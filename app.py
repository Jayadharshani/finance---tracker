import streamlit as st
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #f0f4f8; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(160deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    }
    section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: white !important;
        border-radius: 10px !important;
        width: 100%;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.2) !important;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        border: none !important;
    }

    /* Section headers */
    h2, h3 { color: #1a1a2e !important; }

    /* Dataframe */
    .stDataFrame { border-radius: 12px; overflow: hidden; }

    /* Info / success / warning boxes */
    .stAlert { border-radius: 12px !important; }

    /* AI response box */
    .ai-box {
        background: linear-gradient(135deg, #667eea22, #764ba222);
        border-left: 4px solid #667eea;
        border-radius: 12px;
        padding: 20px 24px;
        margin: 12px 0;
        color: #1a1a2e;
        font-size: 15px;
        line-height: 1.7;
    }

    /* Chat bubble user */
    .chat-user {
        background: #e8f0fe;
        border-radius: 12px 12px 4px 12px;
        padding: 10px 16px;
        margin: 6px 0;
        font-weight: 500;
        color: #1a1a2e;
        text-align: right;
    }

    /* Chat bubble AI */
    .chat-ai {
        background: white;
        border-left: 3px solid #667eea;
        border-radius: 4px 12px 12px 12px;
        padding: 10px 16px;
        margin: 6px 0;
        color: #333;
        font-size: 14px;
    }

    /* Quick question buttons */
    div[data-testid="column"] .stButton > button {
        border-radius: 20px !important;
        font-size: 13px !important;
        padding: 4px 14px !important;
        border: 1.5px solid #667eea !important;
        color: #667eea !important;
        background: white !important;
        transition: all 0.2s;
    }
    div[data-testid="column"] .stButton > button:hover {
        background: #667eea !important;
        color: white !important;
    }

    /* Primary Ask AI button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }

    /* Divider */
    hr { border-color: #e0e7ef !important; }

    /* Input fields */
    .stTextInput > div > div > input {
        border-radius: 10px !important;
        border: 1.5px solid #c5cae9 !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px #667eea33 !important;
    }

    /* Section card wrapper */
    .section-card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }

    /* Badge */
    .badge {
        display: inline-block;
        background: #667eea22;
        color: #667eea;
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame({
        'Date': pd.to_datetime(['2026-01-01', '2026-01-05', '2026-01-10', '2026-01-15', '2026-01-20']),
        'Category': ['Food', 'Transport', 'Shopping', 'Food', 'Entertainment'],
        'Amount': [150, 50, 500, 200, 400],
        'Description': ['Breakfast', 'Auto', 'New shirt', 'Lunch', 'Movie']
    })

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'latest_response' not in st.session_state:
    st.session_state.latest_response = None

if 'latest_question' not in st.session_state:
    st.session_state.latest_question = None


# ── AI Function ────────────────────────────────────────────────────────────────
def ask_ai(prompt):
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        return "⚠️ GEMINI_API_KEY not found in Streamlit secrets."

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.4
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ Error {response.status_code}: {response.json().get('error', {}).get('message', response.text)}"
    except Exception as e:
        return f"⚠️ Connection error: {str(e)}"


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 Finance Tracker")
    st.markdown("---")
    st.markdown("### ➕ Add Expense")

    with st.form("add_expense"):
        exp_date = st.date_input("Date", datetime.now())
        exp_category = st.selectbox("Category", [
            "Food", "Transport", "Shopping", "Entertainment",
            "Bills", "Education", "Health", "Other"
        ])
        amount_method = st.radio(
            "Amount input:", ["Quick Select", "Type Exact"],
            horizontal=True, label_visibility="collapsed"
        )
        if amount_method == "Quick Select":
            exp_amount = st.select_slider(
                "Amount (₹)",
                options=[50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000],
                value=100
            )
        else:
            exp_amount = st.number_input("Amount (₹)", min_value=0, value=100, step=1)

        exp_desc = st.text_input("Description", placeholder="e.g. Lunch at café")

        submitted = st.form_submit_button("✅ Add Expense", use_container_width=True)
        if submitted:
            new_row = pd.DataFrame({
                'Date': [pd.to_datetime(exp_date)],
                'Category': [exp_category],
                'Amount': [exp_amount],
                'Description': [exp_desc]
            })
            st.session_state.expenses = pd.concat(
                [st.session_state.expenses, new_row], ignore_index=True
            )
            st.success(f"Added ₹{exp_amount} for {exp_desc or exp_category}")

    st.markdown("---")

    # Summary in sidebar
    df_side = st.session_state.expenses
    if len(df_side) > 0:
        st.markdown("### 📊 Quick Summary")
        st.metric("Total Spent", f"₹{df_side['Amount'].sum():,.0f}")
        st.metric("Transactions", len(df_side))
        st.metric("Top Category", df_side.groupby('Category')['Amount'].sum().idxmax())

    st.markdown("---")
    if st.button("🗑️ Clear All Data", use_container_width=True):
        st.session_state.expenses = pd.DataFrame(
            columns=['Date', 'Category', 'Amount', 'Description']
        )
        st.session_state.chat_history = []
        st.session_state.latest_response = None
        st.session_state.latest_question = None
        st.success("All data cleared!")


# ── Main Content ───────────────────────────────────────────────────────────────
df = st.session_state.expenses

st.markdown("# 💰 AI-Powered Finance Tracker")
st.markdown("Track your expenses and get smart AI insights instantly.")
st.markdown("---")

# ── Key Metrics ────────────────────────────────────────────────────────────────
if len(df) > 0:
    days_tracked = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
    daily_avg = df['Amount'].sum() / days_tracked

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💵 Total Spent", f"₹{df['Amount'].sum():,.0f}")
    col2.metric("📊 Avg Transaction", f"₹{df['Amount'].mean():,.0f}")
    col3.metric("📈 Highest", f"₹{df['Amount'].max():,.0f}")
    col4.metric("🎯 Daily Avg", f"₹{daily_avg:.0f}")
    col5.metric("🔢 Entries", len(df))

    st.markdown("---")

# ── AI Section ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown("### 🤖 AI Financial Advisor")
st.markdown("Ask anything about your spending — get personalized, data-driven advice.")

# Quick question buttons
st.markdown("**Quick questions:**")
qcols = st.columns(5)
quick_questions = [
    ("💰 Save more", "How can I save more money based on my spending?"),
    ("📊 Budget plan", "Create a monthly budget plan for me"),
    ("🔍 Top expense", "Analyse my highest spending category in detail"),
    ("⚠️ Overspending", "Am I overspending anywhere? Give me specific alerts"),
    ("📈 Invest tips", "Give me investment tips suitable for my income level"),
]
for i, (label, question) in enumerate(quick_questions):
    with qcols[i]:
        if st.button(label, key=f"quick_{i}"):
            st.session_state['prefill_question'] = question
            st.rerun()

# Pre-fill from quick button
default_q = st.session_state.pop('prefill_question', '')

col1, col2 = st.columns([5, 1])
with col1:
    user_question = st.text_input(
        "Ask about your finances:",
        value=default_q,
        placeholder="e.g. How can I save money? What's my biggest expense?",
        key="question_input",
        label_visibility="collapsed"
    )
with col2:
    ask_button = st.button("💬 Ask AI", type="primary", use_container_width=True)

# ── AI Logic ───────────────────────────────────────────────────────────────────
if ask_button and user_question:
    if len(df) == 0:
        st.warning("Please add some expenses first before asking for advice!")
    else:
        with st.spinner("🤔 Analysing your spending data..."):
            total = df['Amount'].sum()
            category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
            top_category = category_totals.index[0]
            top_category_amount = category_totals.values[0]
            top_category_pct = (top_category_amount / total * 100)
            days = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
            daily_avg = total / days
            monthly_est = daily_avg * 30

            category_list = "\n".join([
                f"  - {cat}: ₹{amt:.0f} ({amt/total*100:.0f}% of total)"
                for cat, amt in category_totals.items()
            ])

            recent_rows = df.sort_values('Date', ascending=False).head(5)
            recent_text = "\n".join([
                f"  - {row['Date'].strftime('%d %b')}: {row['Category']} ₹{row['Amount']} — {row['Description']}"
                for _, row in recent_rows.iterrows()
            ])

            prompt = f"""You are a personal finance advisor for an Indian user. 
Analyze ONLY the data provided below. Do NOT make up numbers.

=== USER'S REAL SPENDING DATA ===
Period: {days} days tracked
Total spent: ₹{total:,.0f}
Daily average: ₹{daily_avg:.0f}/day
Monthly estimate: ₹{monthly_est:,.0f}/month

Spending by category:
{category_list}

Recent 5 transactions:
{recent_text}

Biggest expense: {top_category} = ₹{top_category_amount:.0f} ({top_category_pct:.0f}% of total)
=================================

User's question: "{user_question}"

STRICT RULES:
1. Start your answer directly — NO greetings like "Hello", "Great question", "Sure!"
2. Use their EXACT ₹ numbers in every point — never use generic placeholders
3. If asked about savings: calculate how much they save by cutting top categories by 10–20%, show the math
4. If asked for tips: give exactly 3–4 numbered, actionable tips with specific ₹ targets
5. If asked about a category: deeply analyse that category from their data
6. If asked for a budget plan: create a realistic monthly plan using their actual spending patterns
7. Always finish with a bold "Next Step:" with a specific ₹ action
8. Never cut off mid-sentence — complete every thought
9. Use ₹ for all amounts. Use emojis sparingly for readability.
"""

            ai_response = ask_ai(prompt)

            st.session_state.chat_history.append({
                'user': user_question,
                'ai': ai_response
            })
            st.session_state.latest_response = ai_response
            st.session_state.latest_question = user_question
            st.rerun()

# Display latest AI response
if st.session_state.latest_response:
    st.markdown(f"**🤖 Response to:** *{st.session_state.latest_question}*")
    st.markdown(
        f'<div class="ai-box">{st.session_state.latest_response}</div>',
        unsafe_allow_html=True
    )

# Chat history
if st.session_state.chat_history:
    with st.expander(f"💬 Chat History ({len(st.session_state.chat_history)} conversations)", expanded=False):
        for chat in reversed(st.session_state.chat_history[-5:]):
            st.markdown(f'<div class="chat-user">🙋 {chat["user"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="chat-ai">🤖 {chat["ai"]}</div>', unsafe_allow_html=True)
            st.markdown("")

st.markdown('</div>', unsafe_allow_html=True)

# ── Charts ─────────────────────────────────────────────────────────────────────
if len(df) > 0:
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 📊 Spending by Category")
        category_data = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        st.bar_chart(category_data, height=280)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 📈 Daily Spending Trend")
        daily = df.groupby('Date')['Amount'].sum()
        st.line_chart(daily, height=280)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Category Summary ───────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 💰 Category Summary")
    category_summary = df.groupby('Category')['Amount'].sum().reset_index()
    category_summary['Percentage'] = (
        category_summary['Amount'] / category_summary['Amount'].sum() * 100
    ).round(1)
    category_summary['Percentage'] = category_summary['Percentage'].astype(str) + '%'
    category_summary = category_summary.sort_values('Amount', ascending=False)
    category_summary.columns = ['Category', 'Amount (₹)', 'Percentage']
    st.dataframe(category_summary, hide_index=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Smart Alerts ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 🚨 Smart Alerts")

    alerts = []
    category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
    days = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
    daily_avg = df['Amount'].sum() / days

    if len(df) >= 7:
        df_sorted = df.sort_values('Date')
        recent_week = df_sorted.tail(7)['Amount'].sum()
        if len(df) >= 14:
            previous_week = df_sorted.iloc[-14:-7]['Amount'].sum()
            if previous_week > 0:
                change = ((recent_week - previous_week) / previous_week) * 100
                if change > 20:
                    alerts.append(("warning", f"🚨 Spending is UP {change:.1f}% compared to last week!"))
                elif change < -20:
                    alerts.append(("success", f"✅ Great job! Spending is DOWN {abs(change):.1f}% vs last week."))

    top_cat = category_totals.index[0]
    top_amt = category_totals.values[0]
    pct = (top_amt / df['Amount'].sum()) * 100
    if pct > 35:
        alerts.append(("warning", f"💡 {top_cat} makes up {pct:.1f}% of your total spending — consider reviewing this."))

    alerts.append(("info", f"🎯 Your daily spending average is ₹{daily_avg:.0f}. Monthly estimate: ₹{daily_avg*30:,.0f}"))

    freq = df['Category'].value_counts()
    if len(freq) > 0 and freq.values[0] >= 3:
        alerts.append(("info", f"📈 You've transacted in {freq.index[0]} {freq.values[0]} times — your most frequent category."))

    if df['Amount'].max() > daily_avg * 3:
        big = df.loc[df['Amount'].idxmax()]
        alerts.append(("warning", f"⚡ Large transaction detected: ₹{big['Amount']} on {big['Description'] or big['Category']}"))

    for alert_type, message in alerts:
        if alert_type == "warning":
            st.warning(message)
        elif alert_type == "success":
            st.success(message)
        else:
            st.info(message)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Transactions Table ─────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 📋 All Transactions")
    with col2:
        csv = df.to_csv(index=False)
        st.download_button("📥 Export CSV", csv, "expenses.csv", "text/csv", use_container_width=True)

    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%d %b %Y')
    display_df = display_df.sort_values('Date', ascending=False)
    display_df.columns = ['Date', 'Category', 'Amount (₹)', 'Description']
    st.dataframe(display_df, hide_index=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Statistics ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 📊 Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Expense Breakdown**")
        stats_data = {
            "Total": f"₹{df['Amount'].sum():,.0f}",
            "Mean": f"₹{df['Amount'].mean():,.2f}",
            "Median": f"₹{df['Amount'].median():,.2f}",
            "Highest": f"₹{df['Amount'].max():,.2f}",
            "Lowest": f"₹{df['Amount'].min():,.2f}",
        }
        for k, v in stats_data.items():
            st.markdown(f"- **{k}:** {v}")
    with col2:
        st.markdown("**Tracking Info**")
        info_data = {
            "Entries": len(df),
            "Categories": df['Category'].nunique(),
            "Days tracked": days,
            "Avg/day": f"₹{daily_avg:.0f}",
            "Monthly est.": f"₹{daily_avg*30:,.0f}",
        }
        for k, v in info_data.items():
            st.markdown(f"- **{k}:** {v}")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("👋 Add your first expense using the sidebar to get started!")

st.markdown("---")
st.caption("💰 AI Finance Tracker • Powered by Gemini AI")
