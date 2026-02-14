import streamlit as st
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01', '2026-01-05', '2026-01-10', '2026-01-15', '2026-01-20']),
        'Category': ['Food', 'Transport', 'Shopping', 'Food', 'Entertainment'],
        'Amount': [150, 50, 500, 200, 400],
        'Description': ['Breakfast', 'Auto', 'New shirt', 'Lunch', 'Movie']
    })

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

def ask_ai(question, context):
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]  
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": context + "\n\nQuestion: " + question}],
        "temperature": 0.7,
        "max_tokens": 500
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Error {response.status_code}"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

st.title("💰 AI-Powered Finance Tracker")
st.markdown("Track expenses and chat with AI for smart insights!")
st.markdown("---")

with st.sidebar:
    st.header("➕ Add New Expense")
    with st.form("add_expense"):
        exp_date = st.date_input("Date", datetime.now())
        exp_category = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Education", "Health", "Other"])
        amount_method = st.radio("Amount input:", ["Quick Select", "Type Exact"], horizontal=True, label_visibility="collapsed")
        if amount_method == "Quick Select":
            exp_amount = st.select_slider("Amount (₹)", options=[50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000], value=100)
        else:
            exp_amount = st.number_input("Amount (₹)", min_value=0, value=100, step=1)
        exp_desc = st.text_input("Description")
        if st.form_submit_button("Add Expense"):
            new_row = pd.DataFrame({'Date': [pd.to_datetime(exp_date)], 'Category': [exp_category], 'Amount': [exp_amount], 'Description': [exp_desc]})
            st.session_state.expenses = pd.concat([st.session_state.expenses, new_row], ignore_index=True)
            st.success(f"✅ Added: {exp_desc} - ₹{exp_amount}")
            st.rerun()
    st.markdown("---")
    if st.button("🗑️ Clear All Data"):
        st.session_state.expenses = pd.DataFrame(columns=['Date', 'Category', 'Amount', 'Description'])
        st.session_state.chat_history = []
        st.rerun()

df = st.session_state.expenses

st.subheader("🤖 Ask AI Financial Advisor")
st.markdown("*Get personalized advice based on your spending!*")

col1, col2 = st.columns([4, 1])
with col1:
    user_question = st.text_input("Ask about your finances:", placeholder="e.g., How can I save money? What's my biggest expense?", label_visibility="collapsed")
with col2:
    ask_button = st.button("💬 Ask AI", type="primary")

if ask_button and user_question:
    with st.spinner("🤔 AI is analyzing..."):
        total = df['Amount'].sum()
        categories = df.groupby('Category')['Amount'].sum().to_dict()
        recent = df.tail(10)[['Date', 'Category', 'Amount', 'Description']].to_string()
        
    context = f"""You're a friendly finance advisor.

Spending: ₹{total:,.0f}
Categories: {categories}

Answer in 3 SHORT bullet points:
💰 [spending fact]
💡 [one tip]
✅ [encouragement]

Keep each bullet under 15 words with emojis ."""
        
if st.session_state.chat_history:
    with st.expander("💬 Chat History"):
        for idx, chat in enumerate(reversed(st.session_state.chat_history[-5:]), 1):
            st.markdown(f"**Q{idx}:** {chat['user']}")
            st.info(chat['ai'])
            if idx < len(st.session_state.chat_history):
                st.markdown("---")

st.markdown("---")

if len(df) > 0:
    st.subheader("📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 Total Spent", f"₹{df['Amount'].sum():,.0f}")
    col2.metric("📊 Avg Transaction", f"₹{df['Amount'].mean():,.0f}")
    col3.metric("📈 Highest", f"₹{df['Amount'].max():,.0f}")
    col4.metric("🔢 Entries", len(df))
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Spending by Category")
        category_data = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        st.bar_chart(category_data)
    with col2:
        st.subheader("📈 Daily Trend")
        daily = df.groupby('Date')['Amount'].sum()
        st.line_chart(daily)
    
    st.markdown("---")
    st.subheader("💰 Category Summary")
    category_summary = df.groupby('Category')['Amount'].sum().reset_index()
    category_summary['Percentage'] = (category_summary['Amount'] / category_summary['Amount'].sum() * 100).round(1)
    category_summary = category_summary.sort_values('Amount', ascending=False)
    st.dataframe(category_summary, hide_index=True)
    
    st.markdown("---")
    st.subheader("🚨 Smart Alerts")
    alerts = []
    category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
    
    if len(df) >= 7:
        df_sorted = df.sort_values('Date')
        recent_week = df_sorted.tail(7)['Amount'].sum()
        if len(df) >= 14:
            previous_week = df_sorted.iloc[-14:-7]['Amount'].sum()
            if previous_week > 0:
                change = ((recent_week - previous_week) / previous_week) * 100
                if change > 20:
                    alerts.append(("warning", f"🚨 Spending UP {change:.1f}% this week!"))
                elif change < -20:
                    alerts.append(("success", f"✅ Spending DOWN {abs(change):.1f}% this week!"))
    
    top_category = category_totals.index[0]
    top_amount = category_totals.values[0]
    percentage = (top_amount / df['Amount'].sum()) * 100
    if percentage > 35:
        alerts.append(("info", f"💡 {top_category} is {percentage:.1f}% of spending"))
    
    days = (df['Date'].max() - df['Date'].min()).days + 1
    daily_avg = df['Amount'].sum() / days
    alerts.append(("info", f"🎯 Daily avg: ₹{daily_avg:.0f}"))
    
    freq = df['Category'].value_counts()
    if len(freq) > 0 and freq.values[0] >= 3:
        alerts.append(("info", f"📈 {freq.index[0]} appears {freq.values[0]} times"))
    
    for alert_type, message in alerts:
        if alert_type == "warning":
            st.warning(message)
        elif alert_type == "success":
            st.success(message)
        else:
            st.info(message)
    
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 All Transactions")
    with col2:
        csv = df.to_csv(index=False)
        st.download_button("📥 CSV", csv, "expenses.csv")
    
    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df.sort_values('Date', ascending=False), hide_index=True)
    
    st.markdown("---")
    st.subheader("📊 Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Expenses:**")
        st.write(f"- Total: ₹{df['Amount'].sum():,.0f}")
        st.write(f"- Mean: ₹{df['Amount'].mean():,.2f}")
        st.write(f"- Median: ₹{df['Amount'].median():,.2f}")
        st.write(f"- Max: ₹{df['Amount'].max():,.2f}")
        st.write(f"- Min: ₹{df['Amount'].min():,.2f}")
    with col2:
        st.write("**Info:**")
        st.write(f"- Entries: {len(df)}")
        st.write(f"- Categories: {df['Category'].nunique()}")
        st.write(f"- Days tracked: {days}")
        st.write(f"- Avg/day: ₹{daily_avg:.0f}")
else:
    st.info("👋 Add your first expense!")

st.markdown("---")
st.caption("💰 AI Finance Tracker • Powered by Groq AI")
