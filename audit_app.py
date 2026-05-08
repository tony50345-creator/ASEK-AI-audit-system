import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
import re

st.set_page_config(page_title="ASE AI 智慧稽核系統 (通泛邏輯強化版)", layout="wide")

# ==========================================
# 1. 🔑 金鑰載入
# ==========================================
if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("❌ 找不到 API_KEY！")
    st.stop()

MODEL_NAME = "models/gemini-2.5-flash" 

# ==========================================
# 2. 📂 讀取 ARR_checklist.csv (僅作為代碼字典)
# ==========================================
@st.cache_data
def load_matrix():
    encodings = ["utf-8-sig", "big5", "cp950", "utf-8"]
    for enc in encodings:
        try:
            df = pd.read_csv("ARR_checklist.csv", encoding=enc)
            return df.to_string()
        except: continue
    return "ERROR_READ"

MATRIX_DICTIONARY = load_matrix()

# ==========================================
# 3. 🧠 通泛性判定邏輯 (Universal Auditing Framework)
# ==========================================
STRICT_SYSTEM_PROMPT = f"""
你是一位極度嚴謹、具備『通泛邏輯』判定能力的 ASE 品質稽核專家。
你必須避免因關鍵字干擾而產生判定漂移，請遵循以下通用的『稽核常識』框架：

【內部對標字典】：
{MATRIX_DICTIONARY}

【🛡️ 通訊性判定三大法則 (必須嚴格遵守)】：

1. **實體歸屬鎖 (防止 VDA 判定偏移)**：
   - 判定前必須先確認『受稽核實體』。
   - 若受稽核對象為『組織內部資源/流程』(如: 廠務、庫存、人員、設備、內部環境) -> 條位必須鎖定在 VDA 6.3 P5, P6 或 P7。
   - 只有當受稽核對象涉及『外部供應商選擇、評鑑、合約』或『與客戶的合約簽署』 -> 才可進入 VDA 6.3 P2 或 P3。
   - **禁止** 僅因出現『採購』、『合約』等字眼就誤判為 P3，必須看該動作是內部作業還是外部界面管理。

2. **母子項層級鎖 (ISO/IATF 垂直對齊)**：
   - IATF 16949 是 ISO 9001 的增補。你必須先鎖定 ISO 9001 的『章節主軸』(如: 7.支援、8.營運)。
   - 接著在此主軸下，推導對應的 IATF 增補要求，確保兩者章節邏輯完全對稱。

3. **標準化潤飾鎖 (Teacher Mode)**：
   - 步驟 1：將原始紀錄潤飾為『專業稽核描述』(格式：[主體]+[情境]+[缺失事實])。
   - 步驟 2：使用『潤飾後的描述』作為唯一的判定依據，這能確保相同語意的事項在不同時間點獲得一致的判定結果。

【輸出規定】：
- 條文顯示：僅顯示『編號 + 中文標題』。
- 找不到條文：呈現『N/A (原因描述：具體點出是因資訊不足、非 QMS 範疇、或與特定標準衝突)』。
- 不符合分類：Acceptable 為『-』；其餘缺失必須從 C1~C8 判定。

【🚨 JSON 輸出格式】：
{{
  "潤飾筆記": "專業且言簡意賅的稽核描述",
  "代碼": "AXXXX 中文名稱",
  "等級": "Acceptable/Major/Minor/OFI",
  "分類": "C1~C8 或 -",
  "ISO": "編號+標題或N/A(原因)",
  "IATF": "編號+標題或N/A(原因)",
  "VDA": "條目+標題或N/A(原因)",
  "建議": "針對該事項提供 key point 建議或專業詢問手法"
}}
"""

def analyze_audit_process(items):
    model = genai.GenerativeModel(model_name=MODEL_NAME, generation_config={"temperature": 0}, system_instruction=STRICT_SYSTEM_PROMPT)
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, item in enumerate(items):
        if not str(item).strip(): continue
        try:
            response = model.generate_content(f"請依據通泛邏輯進行稽核判定：'{item}'")
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            
            if json_match:
                res = json.loads(json_match.group())
            else:
                res = {{"潤飾筆記": item, "代碼": "A2700 其他事項", "等級": "Acceptable", "分類": "-", "ISO": "N/A", "IATF": "N/A", "VDA": "N/A", "建議": "格式異常"}}

            # Python 後端邏輯加固
            grade = str(res.get("等級", "Acceptable")).strip()
            inconform_cat = str(res.get("分類", "-")).strip()
            if grade == "Acceptable": inconform_cat = "-"
            elif inconform_cat == "-" or "C" not in inconform_cat: inconform_cat = "C2"

            all_results.append({
                "原始紀錄": str(item),
                "專業稽核筆記 (潤飾)": res.get("潤飾筆記", "-"),
                "Category Check Item": res.get("代碼", "A2700 其他事項"),
                "缺失等級": grade,
                "不符合分類": inconform_cat,
                "ISO 9001 條文": res.get("ISO", "N/A"),
                "IATF 16949 條文": res.get("IATF", "N/A"),
                "VDA 6.3 條目": res.get("VDA", "N/A"),
                "建議與備註": res.get("建議", "-")
            })
            time.sleep(0.5)
        except Exception as e:
            all_results.append({"原始紀錄": item, "專業稽核筆記 (潤飾)": f"系統異常: {e}", "Category Check Item": "A2700"})
            
        progress_bar.progress((idx + 1) / len(items))
    return pd.DataFrame(all_results)

# ==========================================
# 4. 🖥️ 介面
# ==========================================
st.title("🛡️ ASE AI 智慧稽核系統 (通泛邏輯強化版)")
st.info("💡 採用『實體歸屬鎖』與『層級演繹法則』，主動預防因關鍵字誤導產生的判定再發。")

uploaded_file = st.file_uploader("上傳 Excel 或 CSV 稽核清單", type=["xlsx", "csv"])
input_df = pd.DataFrame({"稽核紀錄事項": [""] * 3})
edited_df = st.data_editor(input_df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 執行通泛一致性分析"):
    records = []
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                for enc in ["utf-8-sig", "big5", "cp950"]:
                    try:
                        df = pd.read_csv(uploaded_file, encoding=enc)
                        break
                    except: continue
            else:
                df = pd.read_excel(uploaded_file)
            records.extend(df.iloc[:, 0].dropna().tolist())
        except Exception as e: st.error(f"檔案讀取失敗: {e}")
            
    records.extend([r for r in edited_df["稽核紀錄事項"].dropna().tolist() if str(r).strip() != ""])
    
    if records:
        final_df = analyze_audit_process(records)
        st.write("### 📊 專家一致性判定報告")
        st.dataframe(final_df.astype(str), use_container_width=True)
        
        output = io.BytesIO()
        final_df.to_excel(output, index=False)
        st.download_button("📥 下載 Excel 完整報告", output.getvalue(), file_name="ASE_Audit_Report.xlsx")
    else:
        st.warning("請先提供稽核紀錄內容！")
