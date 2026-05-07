import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
import re

st.set_page_config(page_title="ASE AI 智慧稽核系統 (矩陣同步版)", layout="wide")

# ==========================================
# 1. 🔑 金鑰載入
# ==========================================
if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("❌ 找不到 API_KEY！請檢查 Secrets 設定。")
    st.stop()

MODEL_NAME = "models/gemini-2.5-flash" 

# ==========================================
# 2. 📂 讀取更新後的 ARR_checklist.csv
# ==========================================
@st.cache_data
def load_matrix():
    encodings = ["utf-8-sig", "big5", "cp950", "utf-8"]
    for enc in encodings:
        try:
            # 讀取妳更新後的 CSV，作為 AXXXX 代碼與中文名稱的唯一來源
            df = pd.read_csv("ARR_checklist.csv", encoding=enc)
            return df.to_string()
        except:
            continue
    return "ERROR_READ"

MATRIX_DICTIONARY = load_matrix()

# ==========================================
# 3. 🧠 專業稽核分析函式 (字典對標 + 法規專家模式)
# ==========================================
STRICT_SYSTEM_PROMPT = f"""
你是一位資深的 ASE 品質稽核專家，精通 IATF 16949、ISO 9001 與 VDA 6.3。

【專屬對標字典】：
{MATRIX_DICTIONARY}
(說明：請根據此字典內容，嚴格選出最對應的『Category Check Item』代碼與中文名稱)

【任務與輸出規則】：
1. **代碼與名稱**：必須從上述字典中選出代碼 [AXXXX] 與其對應的 [中文名稱]。
   - 格式：AXXXX 中文名稱 (例如: A0305 治具管理流程)
   - 若內容與字典完全無關，則填：A2700 其他事項。
2. **法規判定**：請忽視字典中的法規資訊。請直接根據『稽核紀錄事項』，運用你的專業知識庫找出最新版、最正確的條文。
3. **條文格式**：編號 + 中文標題 (例如: ISO 9001:2015 8.5.1 生產與服務提供之管制)。
4. **缺失邏輯區隔**：
   - 缺失等級：Major, Minor, OFI, Acceptable。
   - 【不符合分類】：若等級為『Acceptable』，此欄位強制填『-』。
   - 【國際條文】：若代碼為『A2700』或真的找不到條文，此欄位強制填『N/A』。

【🚨 JSON 輸出格式】：
{{
  "筆記": "專業分析內容",
  "代碼": "AXXXX 中文名稱",
  "等級": "Acceptable",
  "分類": "-",
  "ISO": "編號+中文標題",
  "IATF": "編號+中文標題",
  "VDA": "條目+中文標題"
}}
"""

def analyze_audit_process(items):
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={"temperature": 0},
        system_instruction=STRICT_SYSTEM_PROMPT
    )
    
    all_results = []
    progress_bar = st.progress(0)
    
    for idx, item in enumerate(items):
        if not str(item).strip(): continue
        try:
            response = model.generate_content(f"稽核事項分析：'{item}'")
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            
            if json_match:
                res = json.loads(json_match.group())
            else:
                res = {"代碼": "A2700 其他事項", "等級": "Acceptable", "分類": "-", "ISO": "N/A", "IATF": "N/A", "VDA": "N/A", "筆記": response.text}

            # --- Python 強制邏輯校正 ---
            grade = str(res.get("等級", "Acceptable")).strip()
            cat_code = str(res.get("代碼", "A2700 其他事項")).strip()
            
            def clean_law(val):
                val = str(val).strip()
                if "A2700" in cat_code or val.upper() in ["", "NAN", "NULL", "NONE", "N/A"]: return "N/A"
                return val

            all_results.append({
                "原始紀錄": str(item),
                "專業稽核筆記": res.get("筆記", "-"),
                "Category Check Item": cat_code,
                "缺失等級": grade,
                "不符合分類": "-" if grade == "Acceptable" else str(res.get("分類", "-")),
                "ISO 9001:2015 條文": clean_law(res.get("ISO", "N/A")),
                "IATF 16949:2016 條文": clean_law(res.get("IATF", "N/A")),
                "VDA 6.3:2023 條目": clean_law(res.get("VDA", "N/A"))
            })
            time.sleep(0.5)
        except Exception as e:
            all_results.append({"原始紀錄": item, "專業稽核筆記": f"解析異常: {e}", "Category Check Item": "A2700 其他事項", "缺失等級": "Acceptable", "不符合分類": "-", "ISO 9001:2015 條文": "N/A", "IATF 16949:2016 條文": "N/A", "VDA 6.3:2023 條目": "N/A"})
            
        progress_bar.progress((idx + 1) / len(items))
    
    return pd.DataFrame(all_results)

# ==========================================
# 4. 🖥️ 介面
# ==========================================
st.title("🛡️ ASE AI 智慧稽核系統 (矩陣精準對標版)")
st.success("✅ 判定標準：已讀取最新的 ARR_checklist.csv 代碼與名稱")

uploaded_file = st.file_uploader("上傳 Excel 或 CSV 稽核清單", type=["xlsx", "csv"])
input_df = pd.DataFrame({"稽核紀錄事項": [""] * 5})
edited_df = st.data_editor(input_df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 執行矩陣對標與分析"):
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
        except Exception as e:
            st.error(f"檔案讀取失敗: {e}")
            
    records.extend([r for r in edited_df["稽核紀錄事項"].dropna().tolist() if str(r).strip() != ""])
    
    if records:
        final_df = analyze_audit_process(records)
        st.write("### 📊 分析結果報告")
        st.dataframe(final_df.astype(str), use_container_width=True)
        
        output = io.BytesIO()
        final_df.to_excel(output, index=False)
        st.download_button("📥 下載 Excel 完整報告", output.getvalue(), file_name="ASE_Audit_Final_Report.xlsx")
    else:
        st.warning("請先輸入或上傳稽核紀錄事項。")
