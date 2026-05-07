import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time

st.set_page_config(page_title="ASE AI 智慧稽核系統 (全相容正式版)", layout="wide")

# ==========================================
# 1. 🔑 雲端金鑰載入
# ==========================================
if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("❌ 找不到 API_KEY！請在 Secrets 設定。")
    st.stop()

MODEL_NAME = "models/gemini-2.5-flash" 

# ==========================================
# 2. 📂 自動偵測編碼讀取 ARR_checklist.csv
# ==========================================
@st.cache_data
def load_matrix():
    # 定義可能的編碼清單 (台灣 Excel 最常出現的幾種)
    encodings = ["utf-8-sig", "big5", "cp950", "utf-8", "gbk"]
    
    for enc in encodings:
        try:
            df_matrix = pd.read_csv("ARR_checklist.csv", encoding=enc)
            # 成功讀取就回傳字串內容
            return df_matrix.to_string()
        except UnicodeDecodeError:
            continue # 失敗就試下一種
        except FileNotFoundError:
            return "ERROR_NOT_FOUND"
        except Exception as e:
            return f"ERROR_READ_GENERAL: {e}"
            
    return "ERROR_ENCODING: 無法解析 CSV 編碼，請嘗試在 Excel 另存為 'CSV UTF-8 (逗號分隔)'"

MATRIX_DICTIONARY = load_matrix()

# 檢查檔案狀態
if MATRIX_DICTIONARY == "ERROR_NOT_FOUND":
    st.warning("⚠️ 尚未偵測到 'ARR_checklist.csv'。請確認檔案已上傳至 GitHub 根目錄。")
    st.stop()
elif "ERROR" in MATRIX_DICTIONARY:
    st.error(f"❌ {MATRIX_DICTIONARY}")
    st.stop()

# ==========================================
# 3. 🧠 專業稽核分析函式
# ==========================================
STRICT_SYSTEM_PROMPT = f"""
你是一位嚴謹的 ASE 專業稽核員。

【對標字典 - 唯一真理】：
{MATRIX_DICTIONARY}

【分類規則】：
1. 必須從上方字典找出最符合的 [AXXXX] 代碼。
2. 禁止發明代碼。若找不到，歸類為 [A2700] (其他事項)。

【判定規範】：
1. 缺失等級：Major, Minor, OFI, Acceptable。
2. 不符合分類：有缺失填代碼(如 C2)；無缺失，必須填寫「-」。
3. 國際條文：填寫繁體中文。若歸類為 A2700，填寫 N/A。

【🚨 JSON 輸出格式 (不可變更)】：
"專業稽核筆記", "Category Check Item", "缺失等級", "不符合分類", "ISO_條文", "IATF_條文", "VDA_條目"
"""

def analyze_audit_process(items):
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={"temperature": 0},
        system_instruction=STRICT_SYSTEM_PROMPT
    )
    
    all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, item in enumerate(items):
        if not str(item).strip(): continue
        status_text.text(f"⚡ 正在進行矩陣比對：{idx+1}/{len(items)} ...")
        
        try:
            response = model.generate_content(f"分析紀錄：'{item}'。請回傳 JSON。")
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            res_dict = json.loads(raw_text)
            if isinstance(res_dict, list): res_dict = res_dict[0]
            
            non_conform = str(res_dict.get("不符合分類", "-")).strip()
            if non_conform.upper() in ["N/A", "無", "NONE", ""]: non_conform = "-"
            
            all_results.append({
                "原始紀錄": str(item),
                "專業稽核筆記": str(res_dict.get("專業稽核筆記", "分析完成")),
                "Category Check Item": str(res_dict.get("Category Check Item", "A2700")),
                "缺失等級": str(res_dict.get("缺失等級", "Acceptable")),
                "不符合分類": non_conform,
                "ISO 9001:2025 條文": str(res_dict.get("ISO_條文", "N/A")),
                "IATF 16949:2016 條文": str(res_dict.get("IATF_條文", "N/A")),
                "VDA 6.3:2023 條目": str(res_dict.get("VDA_條目", "N/A"))
            })
            time.sleep(0.5)
        except Exception as e:
            all_results.append({"原始紀錄": item, "專業稽核筆記": f"分析失敗: {e}", "Category Check Item": "A2700"})
            
        progress_bar.progress((idx + 1) / len(items))
    
    status_text.empty()
    return pd.DataFrame(all_results)

# ==========================================
# 4. 🖥️ 介面
# ==========================================
st.title("🛡️ ASE AI 智慧稽核系統 (全相容正式版)")
st.success(f"✅ ARR 稽核清單載入成功！系統已就緒。")

st.subheader("📤 第一步：上傳待稽核紀錄 (Excel 或 CSV)")
uploaded_file = st.file_uploader("選擇您的檔案", type=["xlsx", "csv"])

st.subheader("✍️ 或者：手動貼入紀錄")
input_df = pd.DataFrame({"稽核紀錄事項": [""] * 5})
edited_df = st.data_editor(input_df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 開始智慧批次對標"):
    records = []
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                # 這裡也要用自動編碼偵測
                for enc in ["utf-8-sig", "big5", "cp950"]:
                    try:
                        df = pd.read_csv(uploaded_file, encoding=enc)
                        break
                    except:
                        continue
            else:
                df = pd.read_excel(uploaded_file)
            records.extend(df.iloc[:, 0].dropna().tolist())
        except Exception as e:
            st.error(f"檔案讀取失敗: {e}")
    
    manual_records = edited_df["稽核紀錄事項"].dropna().tolist()
    records.extend([r for r in manual_records if str(r).strip() != ""])
    
    if records:
        final_df = analyze_audit_process(records)
        st.write("### 📊 分析結果")
        st.dataframe(final_df.astype(str), use_container_width=True)
        
        output = io.BytesIO()
        final_df.astype(str).to_excel(output, index=False)
        st.download_button("📥 下載 Excel 報告", output.getvalue(), file_name="ASE_Audit_Report.xlsx")
    else:
        st.warning("請輸入內容或上傳檔案！")
