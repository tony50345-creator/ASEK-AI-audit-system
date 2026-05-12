import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
import re

# ==========================================
# 0. 網頁配置
# ==========================================
st.set_page_config(page_title="🛡️ 莊大帥 AI 智慧稽核系統 (2.5 旗艦版)", layout="wide")

# ==========================================
# 1. 🔑 API 金鑰與引擎
# ==========================================
if "API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["API_KEY"])
else:
    st.error("❌ 找不到 API_KEY！請檢查 .streamlit/secrets.toml")
    st.stop()

# 使用大帥診斷出的 2.5 Flash 引擎
MODEL_NAME = "models/gemini-2.5-flash" 

# ==========================================
# 2. 📂 讀取對標字典 (ARR_checklist.csv)
# ==========================================
@st.cache_data
def load_matrix():
    encodings = ["utf-8-sig", "big5", "cp950", "utf-8"]
    for enc in encodings:
        try:
            df = pd.read_csv("ARR_checklist.csv", encoding=enc)
            return df.to_string(index=False)
        except:
            continue
    return "無法讀取字典檔案。"

MATRIX_DICTIONARY = load_matrix()

# ==========================================
# 3. 🧠 首席稽核專家 System Prompt (版次鎖定版)
# ==========================================
STRICT_SYSTEM_PROMPT = f"""
你是一位極度嚴謹的「ASE 首席品質稽核專家」。請依據最新國際標準分析稽核紀錄。

【📚 核心對標字典】：
{MATRIX_DICTIONARY}

<<<<<<< HEAD
🔒 核心原則 1：全章節「主項對稱」硬鎖定】

判定權限：完全無視 CSV 對標，直接調用大腦中 ISO 9001:2015、IATF 16949:2016、VDA 6.3:2023 最新版。

🚫 萬用章節對齊公式 (Mandatory)：

前綴絕對一致：IATF 條文的前兩位（或前三位）數字必須與 ISO 完全相同。

邏輯範式：

若 ISO = X.y.z，則 IATF 必須在 X.y.z 系列中。

嚴禁語意偏移：即便 IATF 8.x 的內容更像筆記內容，只要 ISO 鎖定在 7.x，IATF 就絕對禁止跳到 8.x。必須在 IATF 的 7.x 中找增修項（如 7.1.3.1）。

全章節適用：此規則強制適用於第 4 章至第 10 章所有條文。

保底機制：若 IATF 在該 ISO 章節下沒有對應的「.1, .2...」增修內容，請直接重複輸出 ISO 的編號與標題。

輸出格式規範：

純淨輸出：僅限「編號 + 中文標題」。

年份禁令：絕對禁止出現「:2015」或「:2016」。

VDA 限制：僅限輸出 P2 至 P7。

=======
>>>>>>> abaf90069611395fc7fb15a610d8c758500192df
【🔒 核心原則 1：最新標準版次意識】
- 你的分析邏輯必須基於：ISO 9001:2015、IATF 16949:2016、VDA 6.3:2023。
- **輸出限制**：在 ISO、IATF、VDA 欄位中，僅輸出「編號 + 中文標題」。
- **基於筆記找法規 (核心要求)**：【不要參考 CSV 檔中的法規對應】。請直接基於你大腦中最新的國際標準知識庫 (ISO 9001:2015, IATF 16949:2016, VDA 6.3:2023)，為「專業稽核筆記」找出最精準、最合適的條文。
<<<<<<< HEAD
- **邏輯公式：若 ISO 判定為 X.y，則 IATF 必須鎖定在 X.y 或其子項。
- **範例：若 ISO 為 7.1.3，IATF 就必須在 7.x 內尋找（如 7.1.3.1）；嚴禁發生 ISO 選 7.x 但 IATF 選 8.x 的邏輯錯誤！
- **保底方案：若 IATF 沒有特定增修項，請直接重複輸出與 ISO 相同的條文編號。
=======
- **若 ISO 對標為 8.x，IATF 就必須對標 8.x。嚴禁發生 ISO 選 7.x 但 IATF 選 8.x 的邏輯錯誤！
>>>>>>> abaf90069611395fc7fb15a610d8c758500192df
- **嚴禁顯示年份**：例如，應輸出「8.5.1 生產和服務提供的控制」，絕對禁止出現「:2015」或「:2016」等字樣。

【🔒 核心原則 2：潤飾與本質一致性】
- **專業潤飾**：將原始紀錄轉化為中性專業術語。
- **忠於原意**：絕對禁止將「通過 (Acceptable)」的紀錄改寫為具有缺失傾向的語句。

【🔒 核心原則 3：Category Check Item 歸類】
- **參考清單**：請參考以下提供的代碼清單進行 AXXXX 代碼歸類：
  {MATRIX_DICTIONARY}
- **A2700 防呆**：若在清單中找不到與「專業稽核筆記」高度契合的代碼，請統一歸類為「A2700 其他」。

【🔒 核心原則 4：條文範疇與 N/A】
- **ISO / IATF**：章節必須同步 (如 8.x 對 8.x)。
- **VDA 6.3**：僅限 **P2~P7**。嚴禁輸出 Q 開頭編號。
- **防瞎掰**：字典中找不到的條文，必須輸出 "N/A"。

【🔒 核心原則 5：缺失等級 (Grade) 選擇範圍】：
- **Major** (嚴重缺失)
- **Minor** (一般缺失)
- **OFI** (改善機會)
- **Acceptable** (通過)

【🔒 核心原則 6：不符合分類 (Category) 輸出格式】：
若等級非 Acceptable，分類必須輸出「CX 中文描述」。選項如下：
- **C1 系統未定義** | **C2 定義未遵循** | **C3 做了未文件化** | **C4 程序不清**
- **C5 程序不符合** | **C6 缺失重複** | **C7 改善機會** | **C8 觀察事項**
* 注意：若等級為 Acceptable，分類必須固定輸出 "**-**"。

🔒 核心原則 7：專家導師建議 (Mandatory Insight)】
- **不論是否為缺失，皆須回覆建議**。
- 建議內容必須包含：
  1. 【深入詢問】：後續稽核時可以再追問的細節。
  2. 【潛在遺漏】：本次紀錄中可能沒看到但很關鍵的檢查點。
  3. 【補強建議】：未來如何讓該項目的執行更加穩健。

【📋 JSON 欄位要求】：
"潤飾"、"代碼"(AXXXX 中文)、"等級"、"分類"、"ISO"、"IATF"、"VDA"、"建議與備註"。
* 絕對警告：任何欄位嚴禁輸出 null 或 None！
"""

def analyze_audit_process(items):
    model = genai.GenerativeModel(
        model_name=MODEL_NAME, 
        generation_config={
            "temperature": 0, 
            "response_mime_type": "application/json"
        }, 
        system_instruction=STRICT_SYSTEM_PROMPT
    )
    
    combined_query = "\n".join([f"紀錄 {idx+1}: {item}" for idx, item in enumerate(items)])
    status = st.empty()
    status.info(f"🚀 2.5 引擎正在分析中 (共 {len(items)} 筆)...")
    
    try:
        start_time = time.time()
        response = model.generate_content(f"請依潤飾後語意執行精準對標，找不到則 N/A：\n{combined_query}")
        results_list = json.loads(response.text)
        
        final_results = []
        for idx, res in enumerate(results_list):
            # 將 AI 產出的結果映射到帶有版次備註的表頭
            final_results.append({
                "原始紀錄": items[idx] if idx < len(items) else "-",
                "專業稽核筆記 (潤飾)": res.get("潤飾", "-"),
                "Category Check Item": res.get("代碼", "A2700 其他"),
                "缺失等級": res.get("等級", "Acceptable"),
                "不符合分類 (CX)": res.get("分類", "-"),
                "ISO 9001 條文 (2015版)": res.get("ISO", "N/A"),
                "IATF 16949 條文 (2016版)": res.get("IATF", "N/A"),
                "VDA 6.3 條目 (2023版)": res.get("VDA", "N/A"),
                "建議與備註": res.get("建議與備註", "-")
            })
            
        end_time = time.time()
        status.success(f"✅ 分析完成！總耗時：{round(end_time - start_time, 2)} 秒")
        return pd.DataFrame(final_results)
    except Exception as e:
        status.error(f"❌ 發生錯誤：{e}")
        return pd.DataFrame([{"原始紀錄": i, "潤飾": "分析失敗"} for i in items])

# ==========================================
# 4. 🖥️ 使用介面
# ==========================================
<<<<<<< HEAD
st.title("🛡️ 莊大帥率率的 AI 智慧稽核系統")
=======
st.title("🛡️ 莊大帥的 AI 智慧稽核系統")
>>>>>>> abaf90069611395fc7fb15a610d8c758500192df
st.markdown("**核心優化：** 國際法規版次鎖定 (ISO:2015 / IATF:2016 / VDA:2023)")

# 初始化輸入區域
if 'input_data' not in st.session_state:
    st.session_state.input_data = pd.DataFrame({"稽核紀錄事項": [""] * 3})

edited_df = st.data_editor(st.session_state.input_data, num_rows="dynamic", use_container_width=True)

if st.button("🚀 執行最新版次精準分析", use_container_width=True):
    records = [r for r in edited_df["稽核紀錄事項"].dropna().tolist() if str(r).strip() != ""]
    if records:
        final_df = analyze_audit_process(records)
        
        # 顯示結果表格
        st.dataframe(final_df.astype(str), use_container_width=True)
        
        # 產生 Excel 下載
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Report')
        st.download_button(
            label="📥 下載最新版次稽核報告 (Excel)",
            data=output.getvalue(),
            file_name="ASE_Smart_Audit_Report_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("請在上方表格輸入稽核紀錄內容！")