import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import json

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# PUT YOUR API KEY HERE! Replace the text below
GEMINI_API_KEY = "AIzaSyB1cMr0MknVxz8N4jIATe4s3jffYX4sd7s "

if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01', '2026-01-05', '2026-01-10', '2026-01-15', '2026-01-20']),
        'Category': ['Food', 'Transport', 'Shopping', 'Food', 'Entertainment'],
        'Amount': [150, 50, 500, 200, 400],
        'Description': ['Breakfast', 'Auto', 'New shirt', 'Lunch', 'Movie']
    })

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

def ask_gemini(question, context):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{
                "text": context + "\n\nUser question: " + question
            }]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ Error {response.status_code}. Check your API key at aistudio.google.com"
    except Exception as e:
        return f"⚠️ Connection error: {str(e)}"

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
st.markdown("*Get personalized financial advice based on your spending!*")

col1, col2 = st.columns([4, 1])
with col1:
    user_question = st.text_input(
        "Ask me anything about your finances:", 
        placeholder="e.g., How can I save ₹5000 next month? What's my biggest expense?",
        label_visibility="collapsed"
    )
with col2:
    ask_button = st.button("💬 Ask AI", type="primary")

if ask_button and user_question:
    with st.spinner("🤔 AI is analyzing your spending patterns..."):
        total = df['Amount'].sum()
        categories = df.groupby('Category')['Amount'].sum().to_dict()
        recent_transactions = df.tail(10)[['Date', 'Category', 'Amount', 'Description']].to_string()
        
        context = f"""You are an expert personal finance advisor helping a user manage their money better.

USER'S SPENDING DATA:
- Total spent: ₹{total:,.0f}
- Spending by category: {categories}

RECENT TRANSACTIONS:
{recent_transactions}

INSTRUCTIONS:
- Provide specific, actionable financial advice
- Use exact numbers from their data
- Be encouraging and helpful
- Keep response concise (3-4 sentences max)
- If suggesting savings, be realistic"""
        
        ai_response = ask_gemini(user_question, context)
        st.session_state.chat_history.append({"user": user_question, "ai": ai_response})
        
        st.markdown("---")
        st.success("✅ AI Financial Advisor says:")
        st.markdown(ai_response)
        st.markdown("---")

if st.session_state.chat_history:
    with st.expander("💬 View Previous Conversations"):
        for idx, chat in enumerate(reversed(st.session_state.chat_history[-5:]), 1):
            st.markdown(f"**Question {idx}:** {chat['user']}")
            st.info(chat['ai'])
            if idx < min(5, len(st.session_state.chat_history)):
                st.markdown("---")

st.markdown("---")

if len(df) > 0:
    st.subheader("📈 Key Performance Indicators")
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
        st.subheader("📈 Daily Spending Trend")
        daily = df.groupby('Date')['Amount'].sum()
        st.line_chart(daily)
    
    st.markdown("---")
    st.subheader("💰 Category Summary")
    category_summary = df.groupby('Category')['Amount'].sum().reset_index()
    category_summary['Percentage'] = (category_summary['Amount'] / category_summary['Amount'].sum() * 100).round(1)
    category_summary = category_summary.sort_values('Amount', ascending=False)
    st.dataframe(category_summary, hide_index=True)
    
    st.markdown("---")
    st.subheader("🚨 Smart Spending Alerts")
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
                    alerts.append(("warning", f"🚨 Spending INCREASED by {change:.1f}% this week! (₹{recent_week:,.0f} vs ₹{previous_week:,.0f})"))
                elif change < -20:
                    alerts.append(("success", f"✅ Great job! Spending DECREASED by {abs(change):.1f}% this week!"))
    
    top_category = category_totals.index[0]
    top_amount = category_totals.values[0]
    percentage = (top_amount / df['Amount'].sum()) * 100
    if percentage > 35:
        alerts.append(("info", f"💡 {top_category} dominates your spending - {percentage:.1f}% of total (₹{top_amount:,.0f})"))
    
    days_tracked = (df['Date'].max() - df['Date'].min()).days + 1
    daily_avg = df['Amount'].sum() / days_tracked
    alerts.append(("info", f"🎯 Daily average: ₹{daily_avg:.0f} (tracking for {days_tracked} days)"))
    
    category_counts = df['Category'].value_counts()
    most_frequent = category_counts.index[0]
    frequency = category_counts.values[0]
    if frequency >= 3:
        alerts.append(("info", f"📈 {most_frequent} appears {frequency} times - your most frequent expense!"))
    
    if alerts:
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
        st.download_button("📥 Download CSV", csv, "expenses.csv", "text/csv")
    
    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df.sort_values('Date', ascending=False), hide_index=True)
    
    st.markdown("---")
    st.subheader("📊 Summary Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Expense Statistics:**")
        st.write(f"- Total: ₹{df['Amount'].sum():,.0f}")
        st.write(f"- Mean: ₹{df['Amount'].mean():,.2f}")
        st.write(f"- Median: ₹{df['Amount'].median():,.2f}")
        st.write(f"- Max: ₹{df['Amount'].max():,.2f}")
        st.write(f"- Min: ₹{df['Amount'].min():,.2f}")
    with col2:
        st.write("**Transaction Info:**")
        st.write(f"- Total Entries: {len(df)}")
        st.write(f"- Unique Categories: {df['Category'].nunique()}")
        st.write(f"- Date Range: {(df['Date'].max() - df['Date'].min()).days + 1} days")
        st.write(f"- Avg per Day: ₹{(df['Amount'].sum() / max(1, (df['Date'].max() - df['Date'].min()).days + 1)):.0f}")
else:
    st.info("👋 Add your first expense using the sidebar to get started!")

st.markdown("---")
st.caption("💰 AI-Powered Finance Tracker • Get smart financial advice • Track spending patterns")
