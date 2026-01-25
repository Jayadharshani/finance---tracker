import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Page setup
st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# Initialize data in session state
if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01', '2026-01-05', '2026-01-10']),
        'Category': ['Food', 'Transport', 'Shopping'],
        'Amount': [150, 50, 500],
        'Description': ['Breakfast', 'Auto', 'New shirt']
    })

# Title
st.title("💰 Personal Finance Tracker")
st.markdown("Track your expenses and visualize spending patterns!")
st.markdown("---")

# Sidebar - Add expense
with st.sidebar:
    st.header("➕ Add New Expense")
    
    with st.form("add_expense"):
        exp_date = st.date_input("Date", datetime.now())
        exp_category = st.selectbox("Category", 
            ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Education", "Health", "Other"])
        exp_amount = st.number_input("Amount (₹)", min_value=0, value=100, step=10)
        exp_desc = st.text_input("Description")
        
        if st.form_submit_button("Add Expense", use_container_width=True):
            new_row = pd.DataFrame({
                'Date': [pd.to_datetime(exp_date)],
                'Category': [exp_category],
                'Amount': [exp_amount],
                'Description': [exp_desc]
            })
            st.session_state.expenses = pd.concat([st.session_state.expenses, new_row], ignore_index=True)
            st.success(f"✅ Added: {exp_desc} - ₹{exp_amount}")
            st.rerun()
    
    st.markdown("---")
    
    if st.button("🗑️ Clear All Data", use_container_width=True):
        st.session_state.expenses = pd.DataFrame(columns=['Date', 'Category', 'Amount', 'Description'])
        st.rerun()

# Main content
df = st.session_state.expenses

if len(df) > 0:
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 Total Spent", f"₹{df['Amount'].sum():,.0f}")
    col2.metric("📊 Avg Transaction", f"₹{df['Amount'].mean():,.0f}")
    col3.metric("📈 Highest", f"₹{df['Amount'].max():,.0f}")
    col4.metric("🔢 Total Entries", len(df))
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Spending by Category")
        category_data = df.groupby('Category')['Amount'].sum().reset_index()
        fig1 = px.pie(category_data, values='Amount', names='Category', hole=0.4)
        fig1.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("Category Breakdown")
        category_sorted = category_data.sort_values('Amount', ascending=True)
        fig2 = px.bar(category_sorted, x='Amount', y='Category', orientation='h', 
                     color='Amount', color_continuous_scale='Blues')
        st.plotly_chart(fig2, use_container_width=True)
    
    # Trend
    st.subheader("📉 Spending Trend")
    daily = df.groupby('Date')['Amount'].sum().reset_index()
    fig3 = px.line(daily, x='Date', y='Amount', markers=True)
    st.plotly_chart(fig3, use_container_width=True)
    
    st.markdown("---")
    
    # Data table
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 All Transactions")
    with col2:
        csv = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "expenses.csv", "text/csv")
    
    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)
    
    # Insights
    st.markdown("---")
    st.subheader(" Insights")
    top_cat = category_data.loc[category_data['Amount'].idxmax()]
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Top Category:** {top_cat['Category']}\n\n₹{top_cat['Amount']:,.0f} ({top_cat['Amount']/df['Amount'].sum()*100:.1f}%)")
    with col2:
        avg_daily = df['Amount'].sum() / max(1, (df['Date'].max() - df['Date'].min()).days + 1)
        st.info(f"**Daily Average:** ₹{avg_daily:,.0f}\n\nBased on your spending pattern")
else:
    st.info(" Add your first expense using the sidebar!")

st.markdown("---")
st.caption("Track daily expenses • Visualize patterns • Make better financial decisions")
