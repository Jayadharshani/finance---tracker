import streamlit as st
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# ---------- SESSION ----------
if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01', '2026-01-05', '2026-01-10', '2026-01-15', '2026-01-20']),
        'Category': ['Food', 'Transport', 'Shopping', 'Food', 'Entertainment'],
        'Amount': [150, 50, 500, 200, 400],
        'Description': ['Breakfast', 'Auto', 'New shirt', 'Lunch', 'Movie']
    })

# ---------- AI FUNCTION ----------
def ask_ai(question, context):
    try:
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    except:
        return "⚠️ API key missing"

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": context + "\n\n" + question}],
        "temperature": 0.3
    }

    res = requests.post(url, headers=headers, json=data)

    if res.status_code == 200:
        return res.json()['choices'][0]['message']['content']
    return "⚠️ AI error"

# ---------- UI STYLE ----------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
}
section[data-testid="stSidebar"] {
    background-color: #111827;
}
[data-testid="metric-container"] {
    background-color: #1e293b;
    padding: 15px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------- TITLE ----------
st.title("💰 AI-Powered Finance Tracker")
st.markdown("---")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("➕ Add Expense")

    with st.form("form"):
        date = st.date_input("Date", datetime.now())
        category = st.selectbox("Category", ["Food","Transport","Shopping","Entertainment"])
        amount = st.number_input("Amount", min_value=0)
        desc = st.text_input("Description")

        if st.form_submit_button("Add"):
            new = pd.DataFrame({
                'Date':[pd.to_datetime(date)],
                'Category':[category],
                'Amount':[amount],
                'Description':[desc]
            })
            st.session_state.expenses = pd.concat([st.session_state.expenses,new], ignore_index=True)
            st.success("Added!")

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

    # ---------- CHARTS (FIXED - NO MATPLOTLIB) ----------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Category Spending")
        st.bar_chart(df.groupby('Category')['Amount'].sum())

    with col2:
        st.subheader("📈 Daily Trend")
        st.line_chart(df.groupby('Date')['Amount'].sum())

    st.markdown("---")

    # ---------- AI ----------
    st.subheader("🤖 AI Advisor")
    question = st.text_input("Ask about your spending")

    if st.button("Ask AI") and question:
        total = df['Amount'].sum()
        top_cat = df.groupby('Category')['Amount'].sum().idxmax()

        context = f"Total ₹{total}, Top category {top_cat}"

        answer = ask_ai(question, context)
        st.success(answer)

    st.markdown("---")

    # ---------- ALERT ----------
    st.subheader("🚨 Alerts")

    food_total = df[df['Category']=="Food"]['Amount'].sum()
    if food_total > 2000:
        st.warning(f"🍔 High food spending: ₹{food_total}")

    # ---------- TABLE ----------
    st.subheader("📋 Transactions")
    st.dataframe(df)

    # ---------- DOWNLOAD ----------
    st.download_button("📥 Download CSV", df.to_csv(index=False), "expenses.csv")

else:
    st.info("Add expenses!")

st.caption("💰 Finance Tracker 🚀")
