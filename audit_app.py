import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
import re

st.set_page_config(page_title="ASE AI 智慧稽核系統 (邏輯精準版)", layout="wide")

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
        except:
            continue
    return "ERROR_READ"

MATRIX_DICTIONARY = load_matrix()

# ==========================================
# 3. 🧠 專業稽核分析函式 (精準對標 A2700/Acceptable 邏輯)
# ==========================================
STRICT_SYSTEM_PROMPT = f"""
你是一位嚴謹的 ASE 專業稽核員。
【專屬字典內容】：
{MATRIX_DICTIONARY}

【任務規則與輸出邏輯】：
1. 必須從字典找出最符合的代碼。格式：[AXXXX] + [中文名稱]。
2. 若找不到對應，代碼填：A2700 其他事項。
3. 缺失等級：Major, Minor, OFI, Acceptable。
4. 【不符合分類】邏輯：
   - 若等級為『Acceptable』，此欄位必須填『-』。
   - 若有缺失，填寫對應代碼。
5. 【國際條文(ISO/IATF/VDA)】邏輯：
   - 若字典中有對應條文，請照實填寫。
   - 若代碼為『A2700』或字典中找不到條文，此欄位必須填『N/A』。

【🚨 JSON 輸出格式】：
{{
  "筆記": "分析內容",
  "代碼": "AXXXX 中文名稱",
  "等級": "Acceptable",
  "分類": "-",
  "ISO": "條文內容或N/A",
  "IATF": "條文內容或N/A",
  "VDA": "條文內容或N/A"
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
            response = model.generate_content(f"分析事項：'{item}'")
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            
            if json_match:
                res = json.loads(json_match.group())
            else:
                res = {"代碼": "A2700 其他事項", "等級": "Acceptable", "分類": "-", "ISO": "N/A", "IATF": "N/A", "VDA": "N/A", "筆記": response.text}

            # --- Python 強制邏輯修整 (防止 AI 遺忘規則) ---
            grade = str(res.get("等級", "Acceptable")).strip()
            cat_code = str(res.get("代碼", "A2700 其他事項")).strip()
            
            # 1. 若無缺失，分類強制為 "-"
            inconform_cat = str(res.get("分類", "-")).strip()
            if grade == "Acceptable" or inconform_cat.upper() in ["NONE", "無", ""]:
                inconform_cat = "-"
            
            # 2. 條文 N/A 邏輯判定
            def fix_law(val):
                val = str(val).strip()
                if "A2700" in cat_code or val.upper() in ["", "NAN", "NULL", "NONE"]:
                    return "N/A"
                return val

            all_results.append({
                "原始紀錄": str(item),
                "專業稽核筆記": res.get("筆記", "-"),
                "Category Check Item": cat_code,
                "缺失等級": grade,
                "不符合分類": inconform_cat,
                "ISO 9001:2015 條文": fix_law(res.get("ISO", "N/A")),
                "IATF 16949:2016 條文": fix_law(res.get("IATF", "N/A")),
                "VDA 6.3:2023 條目": fix_law(res.get("VDA", "N/A"))
            })
            time.sleep(0.5)
        except Exception as e:
            all_results.append({"原始紀錄": item, "專業稽核筆記": f"系統異常: {e}", "Category Check Item": "A2700 其他事項", "缺失等級": "Acceptable", "不符合分類": "-", "ISO 9001:2015 條文": "N/A", "IATF 16949:2016 條文": "N/A", "VDA 6.3:2023 條目": "N/A"})
            
        progress_bar.progress((idx + 1) / len(items))
    
    return pd.DataFrame(all_results)

# ==========================================
# 4. 🖥️ 介面
# ==========================================
st.title("🛡️ ASE AI 智慧稽核系統 (邏輯優化版)")
st.info("✅ 邏輯已鎖定：無缺失顯示『-』 / 找不到條文顯示『N/A』")

uploaded_file = st.file_uploader("上傳 Excel 或 CSV 稽核清單", type=["xlsx", "csv"])
input_df = pd.DataFrame({"稽核紀錄事項": [""] * 5})
edited_df = st.data_editor(input_df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 開始智慧分析"):
    records = []
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
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
        st.download_button("📥 下載 Excel 分析報告", output.getvalue(), file_name="ASE_Audit_Report.xlsx")
    else:
        st.warning("請先提供稽核紀錄內容！")
