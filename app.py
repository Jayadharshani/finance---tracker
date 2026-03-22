import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from data_processing import *
from visualization import *
from utils import *
# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# ---------- CUSTOM CSS (UI DESIGN) ----------
st.markdown("""
<style>
body {
    background-color: #0E1117;
}
.main {
    background: linear-gradient(135deg, #1f4037, #99f2c8);
    padding: 20px;
    border-radius: 10px;
}
h1, h2, h3 {
    color: #ffffff;
}
.stMetric {
    background-color: #1c1c1c;
    padding: 10px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------- SESSION STATE ----------
if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01']),
        'Category': ['Food'],
        'Amount': [100],
        'Description': ['Sample']
    })

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# ---------- AI FUNCTION ----------
def ask_ai(question, context):
    try:
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    except:
        return "⚠️ Error: GROQ_API_KEY not found"

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }

    # ✅ Improved prompt (VERY IMPORTANT)
    full_prompt = f"""
You are a smart financial advisor.

User Data:
{context}

Question: {question}

Rules:
- Answer in 2-3 short sentences
- Give practical advice
- Use numbers if possible
- Keep it simple and clear
"""

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.6,   # slightly more accurate
        "max_tokens": 200
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Error {response.status_code}"
    
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

    res = requests.post(url, headers=headers, json=data)

    if res.status_code == 200:
        return res.json()['choices'][0]['message']['content']
    return "Error in AI response"

# ---------- TITLE ----------
st.title("💰 AI Finance Tracker")
st.caption("Smart expense tracking with AI insights 🚀")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("➕ Add Expense")

    with st.form("expense_form"):
        date = st.date_input("Date", datetime.now())
        category = st.selectbox("Category", ["Food","Transport","Shopping","Entertainment","Bills"])
        amount = st.number_input("Amount", min_value=0)
        desc = st.text_input("Description")

        if st.form_submit_button("Add"):
            new = pd.DataFrame({
                'Date':[pd.to_datetime(date)],
                'Category':[category],
                'Amount':[amount],
                'Description':[desc]
            })
            st.session_state.expenses = pd.concat([st.session_state.expenses, new], ignore_index=True)
            st.success("Added successfully!")

# ---------- DATA ----------
df = st.session_state.expenses

if len(df) > 0:

    # ---------- METRICS ----------
    st.subheader("📊 Overview")
    col1,col2,col3,col4 = st.columns(4)

    col1.metric("Total", f"₹{df['Amount'].sum():,.0f}")
    col2.metric("Avg", f"₹{df['Amount'].mean():,.0f}")
    col3.metric("Max", f"₹{df['Amount'].max():,.0f}")
    col4.metric("Entries", len(df))

    st.markdown("---")

    # ---------- CHARTS ----------
    col1,col2 = st.columns(2)

    with col1:
        st.subheader("Category Spend")
        st.bar_chart(df.groupby('Category')['Amount'].sum())

    with col2:
        st.subheader("Daily Trend")
        st.line_chart(df.groupby('Date')['Amount'].sum())

    st.markdown("---")

    # ---------- AI ----------
    st.subheader("🤖 AI Advisor")

    question = st.text_input("Ask anything about your spending")

    if st.button("Ask AI"):

        total = df['Amount'].sum()
        top_cat = df.groupby('Category')['Amount'].sum().idxmax()

        context = f"""
        Total spend ₹{total}.
        Top category {top_cat}.
        Give short financial advice.
        """

        response = ask_ai(question, context)
        st.success(response)

    st.markdown("---")

    # ---------- TABLE ----------
    st.subheader("📋 Transactions")
    st.dataframe(df, use_container_width=True)

    # ---------- DOWNLOAD ----------
    st.download_button("Download CSV", df.to_csv(index=False), "expenses.csv")

else:
    st.info("Add some expenses!")

st.caption("Built with ❤️ using Streamlit")
