import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import json

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# Your API key - Replace this!
GEMINI_API_KEY = "AIzaSyB1cMr0MknVxz8N4jIATe4s3jffYX4sd7s"

if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01', '2026-01-05', '2026-01-10']),
        'Category': ['Food', 'Transport', 'Shopping'],
        'Amount': [150, 50, 500],
        'Description': ['Breakfast', 'Auto', 'New shirt']
    })

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

def ask_gemini(question, context):
    """Ask Gemini AI using REST API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": f"{context}\n\nUser question: {question}"}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

st.title("💰 AI-Powered Finance Tracker")
st.markdown("Track expenses and chat with AI for insights!")
st.markdown("---")

with st.sidebar:
    st.header("➕ Add New Expense")
    with st.form("add_expense"):
        exp_date = st.date_input("Date", datetime.now())
        exp_category = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Education", "Health", "Other"])
        exp_amount = st.number_input("Amount (₹)", min_value=0, value=100, step=50)
        exp_desc = st.text_input("Description")
        if st.form_submit_button("Add Expense", use_container_width=True):
            new_row = pd.DataFrame({'Date': [pd.to_datetime(exp_date)], 'Category': [exp_category], 'Amount': [exp_amount], 'Description': [exp_desc]})
            st.session_state.expenses = pd.concat([st.session_state.expenses, new_row], ignore_index=True)
            st.success(f"✅ Added: {exp_desc} - ₹{exp_amount}")
            st.rerun()
    st.markdown("---")
    if st.button("🗑️ Clear All Data", use_container_width=True):
        st.session_state.expenses = pd.DataFrame(columns=['Date', 'Category', 'Amount', 'Description'])
        st.rerun()

df = st.session_state.expenses

st.subheader("🤖 Ask AI About Your Finances")

col1, col2 = st.columns([3, 1])
with col1:
    user_question = st.text_input("Ask anything about your expenses:", placeholder="e.g., How much did I spend on food?")
with col2:
    ask_button = st.button("Ask AI", use_container_width=True)

if ask_button and user_question:
    with st.spinner("AI is thinking..."):
        total = df['Amount'].sum()
        categories = df.groupby('Category')['Amount'].sum().to_dict()
        recent = df.tail(5)[['Date', 'Category', 'Amount', 'Description']].to_string()
        
        context = f"""You are a personal finance assistant. Help analyze spending.
        
Total spent: ₹{total}
Spending by category: {categories}
Recent transactions:
{recent}

Give a helpful, concise answer with specific numbers."""
        
        ai_response = ask_gemini(user_question, context)
        st.session_state.chat_history.append({"user": user_question, "ai": ai_response})
        st.success("✅ AI Response:")
        st.write(ai_response)

if st.session_state.chat_history:
    with st.expander("💬 Chat History"):
        for chat in reversed(st.session_state.chat_history[-5:]):
            st.markdown(f"**You:** {chat['user']}")
            st.markdown(f"**AI:** {chat['ai']}")
            st.markdown("---")

st.markdown("---")

if len(df) > 0:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 Total Spent", f"₹{df['Amount'].sum():,.0f}")
    col2.metric("📊 Avg Transaction", f"₹{df['Amount'].mean():,.0f}")
    col3.metric("📈 Highest", f"₹{df['Amount'].max():,.0f}")
    col4.metric("🔢 Total Entries", len(df))
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Spending by Category")
        category_data = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        st.bar_chart(category_data)
    with col2:
        st.subheader("📈 Daily Spending")
        daily = df.groupby('Date')['Amount'].sum()
        st.line_chart(daily)
    
    st.markdown("---")
    st.subheader("🚨 Smart Alerts")
    category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
    if len(category_totals) > 0:
        top_category = category_totals.index[0]
        top_amount = category_totals.values[0]
        percentage = (top_amount / df['Amount'].sum()) * 100
        if percentage > 35:
            st.info(f"💡 {top_category} dominates - {percentage:.1f}% (₹{top_amount:,.0f})")
    
    days_tracked = (df['Date'].max() - df['Date'].min()).days + 1
    daily_avg = df['Amount'].sum() / days_tracked
    st.info(f"🎯 Daily average: ₹{daily_avg:.0f}")
    
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 All Transactions")
    with col2:
        csv = df.to_csv(index=False)
        st.download_button("📥 Download", csv, "expenses.csv", "text/csv")
    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("👋 Add your first expense!")

st.markdown("---")
st.caption("💰 AI-Powered Finance Tracker • Chat with AI for insights")


