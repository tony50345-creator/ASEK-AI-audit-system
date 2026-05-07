import streamlit as st
import requests
import json

# ==========================================
# 1. 填入你剛剛建立的「全新專案」API KEY
# ==========================================
API_KEY = "AIzaSyDeOXmbGpt-VXJ8sk1x7d2UJ3gvtIX1TsE" 

st.set_page_config(page_title="AI 稽核專家", page_icon="🛡️")
st.title("🛡️ AI 國際條文稽核專家 (自動相容版)")

def get_available_model():
    """自動找出這把鑰匙能用的模型名稱"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        models = response.json().get('models', [])
        # 優先找 1.5-flash，找不到就找任何可以生內容的模型
        for m in models:
            if "generateContent" in m.get("supportedGenerationMethods", []):
                if "1.5-flash" in m['name']:
                    return m['name']
        return models[0]['name'] if models else None
    except:
        return None

def analyze_finding(finding):
    model_path = get_available_model()
    if not model_path:
        return "❌ 找不到可用模型，請檢查 API Key 是否正確。"
    
    # 建立連線網址
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": f"你是一位 IATF 16949 專家，請分析此案並給建議：{finding}"}]}]
    }
    
    try:
        res = requests.post(url, json=payload, timeout=30)
        data = res.json()
        if res.status_code == 200:
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ 錯誤 ({res.status_code}): {data.get('error', {}).get('message')}"
    except Exception as e:
        return f"❌ 連線失敗: {str(e)}"

# ==========================================
# 3. 介面
# ==========================================
user_input = st.text_area("請輸入稽核發現 (例如 K08969 的訓練問題)：")

if st.button("🚀 執行 AI 智慧分析"):
    if "AIza" not in API_KEY:
        st.error("請先填入正確的 API Key")
    else:
        with st.spinner("正在尋找可用大腦並分析中..."):
            result = analyze_finding(user_input)
            st.markdown("### 💡 專家分析報告")
            st.write(result)