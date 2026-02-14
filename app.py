import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import json

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# ADD YOUR GEMINI API KEY HERE!
GEMINI_API_KEY = "AIzaSyABzKeUCmOwBahrhh1WpvibAOD95XOfcKY"  # Replace with your actual key

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
    """Fixed Gemini API call"""
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
            return f"⚠️ Error {response.status_code}: Please check API key is active at aistudio.google.com"
            
    except Exception as e:
        return f"⚠️ Connection error: {str(e)}"

st.title("💰 AI-Powered Finance Tracker")
st.markdown("Track expenses, get AI insights, and visualize spending patterns!")
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

# AI CHATBOT SECTION (NEW!)
st.subheader("🤖 Ask AI Financial Assistant")

col1, col2 = st.columns([4, 1])
with col1:
    user_question = st.text_input(
        "Ask anything about your finances:",
        placeholder="e.g., How much did I spend on food? Give me saving tips.",
        label_visibility="collapsed"
    )
with col2:
    ask_btn = st.button("💬 Ask AI", use_container_width=True, type="primary")

if ask_btn and user_question:
    with st.spinner("🤔 AI is analyzing your data..."):
        total = df['Amount'].sum()
        categories = df.groupby('Category')['Amount'].sum().to_dict()
        recent = df.tail(5).to_string(index=False)
        
        context = f"""You are a helpful personal finance assistant. Analyze the user's spending data.

Total spent: ₹{total:,.0f}
Spending by category: {categories}
Recent 5 transactions:
{recent}

Give practical, specific advice with numbers. Be conversational and helpful."""
        
        ai_response = ask_gemini(user_question, context)
        st.session_state.chat_history.append({"q": user_question, "a": ai_answer})
        
        st.success("✅ AI Response:")
        st.markdown(ai_answer)

# Show recent chat history
if len(st.session_state.chat_history) > 0:
    with st.expander("💬 Recent Conversations (Last 3)"):
        for chat in reversed(st.session_state.chat_history[-3:]):
            st.markdown(f"**You:** {chat['q']}")
            st.markdown(f"**AI:** {chat['a']}")
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
        category_data = df.groupby('Category')['Amount'].sum().reset_index()
        st.bar_chart(category_data.set_index('Category'))
    with col2:
        st.subheader("📈 Daily Spending Trend")
        daily = df.groupby('Date')['Amount'].sum().reset_index()
        st.line_chart(daily.set_index('Date'))
    
    st.markdown("---")
    st.subheader("💰 Category Summary")
    category_summary = df.groupby('Category')['Amount'].sum().reset_index()
    category_summary['Percentage'] = (category_summary['Amount'] / category_summary['Amount'].sum() * 100).round(1)
    category_summary = category_summary.sort_values('Amount', ascending=False)
    st.dataframe(category_summary, use_container_width=True, hide_index=True)
    
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
    
    if len(category_totals) > 0:
        top_category = category_totals.index[0]
        top_amount = category_totals.values[0]
        percentage = (top_amount / df['Amount'].sum()) * 100
        if percentage > 35:
            alerts.append(("info", f"💡 {top_category} dominates your spending - {percentage:.1f}% of total (₹{top_amount:,.0f})"))
    
    df_with_day = df.copy()
    df_with_day['DayOfWeek'] = df_with_day['Date'].dt.dayofweek
    weekend = df_with_day[df_with_day['DayOfWeek'].isin([5, 6])]['Amount'].sum()
    weekday = df_with_day[~df_with_day['DayOfWeek'].isin([5, 6])]['Amount'].sum()
    if weekend > 0 and weekday > 0:
        weekend_count = len(df_with_day[df_with_day['DayOfWeek'].isin([5, 6])])
        weekday_count = len(df_with_day[~df_with_day['DayOfWeek'].isin([5, 6])])
        if weekend_count > 0 and weekday_count > 0:
            weekend_avg = weekend / weekend_count
            weekday_avg = weekday / weekday_count
            if weekend_avg > weekday_avg * 1.5:
                alerts.append(("warning", f"⚠️ Weekend spending (₹{weekend_avg:.0f}/day) is {(weekend_avg/weekday_avg):.1f}x higher than weekdays!"))
    
    threshold = df['Amount'].mean() + (2 * df['Amount'].std())
    large_expenses = df[df['Amount'] > threshold]
    if len(large_expenses) > 0:
        for _, expense in large_expenses.head(3).iterrows():
            alerts.append(("error", f"📊 Unusual spike: ₹{expense['Amount']:,.0f} on {expense['Date'].strftime('%Y-%m-%d')} ({expense['Description']})"))
    
    days_tracked = (df['Date'].max() - df['Date'].min()).days + 1
    daily_avg = df['Amount'].sum() / days_tracked
    alerts.append(("info", f"🎯 Daily average: ₹{daily_avg:.0f} (tracking for {days_tracked} days)"))
    
    category_counts = df['Category'].value_counts()
    if len(category_counts) > 0:
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
            elif alert_type == "error":
                st.error(message)
            else:
                st.info(message)
    else:
        st.info("Add more expenses to see personalized alerts!")
    
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 All Transactions")
    with col2:
        csv = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "expenses.csv", "text/csv")
    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("👋 Add your first expense using the sidebar!")

st.markdown("---")
st.caption("💰 AI-Powered Finance Tracker • Ask AI for insights • Smart spending analysis")


