import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
import re

st.set_page_config(page_title="莊大帥的 AI 智慧稽核系統", layout="wide")

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
# 2. 📂 讀取 ARR_checklist.csv
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
# 3. 🧠 專業顧問分析邏輯 (硬邏輯約束版)
# ==========================================
STRICT_SYSTEM_PROMPT = f"""
你是一位極度嚴謹、絕不犯錯的 ASE 首席品質稽核專家。
【絕對禁令】：
- 嚴禁在條文欄位中顯示『ISO 9001』、『IATF 16949』或版本號字眼。
- 嚴禁衍生原始紀錄中未提到的缺失。
- 一致性要求：如果是同樣的現象重複詢問，必須確保每次的判定結果都完全相同。

【對標字典】：{MATRIX_DICTIONARY}

【🔒 硬性判定邏輯】：
1. **母子項垂直同步**：IATF 條文必須是 ISO 9001 條文的延伸。若 ISO 是第 8 章，IATF 絕不能跑去第 7 章。
2. **純事實潤飾**：僅將原始紀錄轉化為專業稽核語言。若無明確異常，等級必須是 Acceptable。
3. **格式清理**：條文僅允許呈現『編號 + 中文標題』。

【分析 SOP】：
Step 1. 潤飾：轉化為專業 ISO 術語。
Step 2. 代碼：對標字典找出 AXXXX。
Step 3. 條文：先定 ISO 編號 -> 再定 IATF 編號 -> 根據主體判定 VDA 條目。
Step 4. 理由：若為 N/A，必須在括號內註明原因。

【JSON 輸出範例】：
{{
  "潤飾": "設備重新配置與配置驗收...",
  "代碼": "A0203 設備重新配置",
  "等級": "Acceptable",
  "分類": "-",
  "ISO": "8.5.1 生產與服務提供之管制",
  "IATF": "8.5.1.1 設備重新配置",
  "VDA": "P6.2.2 過程資源",
  "建議": "確認驗收紀錄之完整性"
}}
"""

def analyze_audit_process(items):
    # 溫度設為 0 確保高度一致性
    model = genai.GenerativeModel(model_name=MODEL_NAME, generation_config={"temperature": 0}, system_instruction=STRICT_SYSTEM_PROMPT)
    all_results = []
    progress_bar = st.progress(0)
    
    # 物理清理函數：強制移除 ISO/IATF 等字眼
    def force_clean(text):
        if not text or text == "-": return "-"
        # 移除常見的標準名稱標籤
        cleaned = re.sub(r'(ISO\s*9001|IATF\s*16949|VDA\s*6\.3|:2015|:2016|:2023)', '', text, flags=re.IGNORECASE)
        return cleaned.strip()

    for idx, item in enumerate(items):
        if not str(item).strip(): continue
        try:
            response = model.generate_content(f"分析：'{item}'")
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            
            if json_match:
                res = json.loads(json_match.group())
            else:
                res = {{"潤飾": item, "代碼": "A2700 其他事項", "等級": "Acceptable", "分類": "-", "ISO": "N/A", "IATF": "N/A", "VDA": "N/A", "建議": "解析失敗"}}

            grade = str(res.get("等級", "Acceptable")).strip()
            
            # 整理結果並進行物理清理
            all_results.append({
                "原始紀錄": str(item),
                "專業稽核筆記 (潤飾)": res.get("潤飾", "-"),
                "Category Check Item": res.get("代碼", "A2700 其他事項"),
                "缺失等級": grade,
                "不符合分類": "-" if grade == "Acceptable" else str(res.get("分類", "C2")),
                "ISO 9001 條文": force_clean(res.get("ISO", "N/A")),
                "IATF 16949 條文": force_clean(res.get("IATF", "N/A")),
                "VDA 6.3 條目": force_clean(res.get("VDA", "N/A")),
                "建議與備註": res.get("建議", "-")
            })
            time.sleep(0.5)
        except Exception as e:
            all_results.append({"原始紀錄": item, "專業稽核筆記 (潤飾)": f"錯誤: {e}", "Category Check Item": "A2700"})
            
        progress_bar.progress((idx + 1) / len(items))
    return pd.DataFrame(all_results)

# ==========================================
# 4. 🖥️ 介面
# ==========================================
st.title("🛡️ 莊大帥的 AI 智慧稽核系統")
st.success("✅ 已啟動：物理格式清洗、母子項強制同步、事實潤飾隔離。")

uploaded_file = st.file_uploader("上傳檔案", type=["xlsx", "csv"])
input_df = pd.DataFrame({"稽核紀錄事項": [""] * 3})
edited_df = st.data_editor(input_df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 執行深度穩定分析"):
    records = []
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            records.extend(df.iloc[:, 0].dropna().tolist())
        except Exception as e: st.error(f"檔案讀取失敗: {e}")
            
    records.extend([r for r in edited_df["稽核紀錄事項"].dropna().tolist() if str(r).strip() != ""])
    
    if records:
        final_df = analyze_audit_process(records)
        st.write("### 📊 稽核報告 (標準一致性鎖定)")
        st.dataframe(final_df.astype(str), use_container_width=True)
        
        output = io.BytesIO()
        final_df.to_excel(output, index=False)
        st.download_button("📥 下載 Excel 報告", output.getvalue(), file_name="ASE_Audit_Report.xlsx")
    else:
        st.warning("請輸入內容！")
