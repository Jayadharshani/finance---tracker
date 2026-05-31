import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import base64
import io

# ── Optional imports ──────────────────────────────────────────────
try:
    from sklearn.linear_model import LinearRegression
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    import pymongo
    MONGO_OK = True
except ImportError:
    MONGO_OK = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import inch
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(page_title="Finance Tracker", page_icon="💰", layout="wide")

# ── Session state defaults ────────────────────────────────────────
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
if 'monthly_budget' not in st.session_state:
    st.session_state.monthly_budget = 10000
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""

# ══════════════════════════════════════════════════════════════════
# 1. GEMINI AI HELPER
# ══════════════════════════════════════════════════════════════════
def ask_ai(question, context):
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except:
        return "⚠️ GEMINI_API_KEY not found in secrets"
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    data = {
        "contents": [{"parts": [{"text": context + "\n\nQuestion: " + question}]}],
        "generationConfig": {"maxOutputTokens": 800, "temperature": 0.7}
    }
    try:
        response = requests.post(url, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return f"⚠️ Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ══════════════════════════════════════════════════════════════════
# 2. MONGODB LOGIN SYSTEM
# ══════════════════════════════════════════════════════════════════
def get_mongo_db():
    if not MONGO_OK:
        return None
    try:
        uri = st.secrets["MONGO_URI"]
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.server_info()
        return client["finance_tracker"]
    except:
        return None

def mongo_register(username, password):
    db = get_mongo_db()
    if db is None:
        return False, "MongoDB not connected"
    if db.users.find_one({"username": username}):
        return False, "Username already exists"
    db.users.insert_one({"username": username, "password": password})
    return True, "Registered!"

def mongo_login(username, password):
    db = get_mongo_db()
    if db is None:
        return False, "MongoDB not connected"
    user = db.users.find_one({"username": username, "password": password})
    if user:
        return True, "Login successful"
    return False, "Invalid credentials"

def mongo_save_expenses(username, df):
    db = get_mongo_db()
    if db is None:
        return
    records = df.copy()
    records['Date'] = records['Date'].astype(str)
    db.expenses.delete_many({"username": username})
    docs = [{"username": username, **r} for r in records.to_dict("records")]
    if docs:
        db.expenses.insert_many(docs)

def mongo_load_expenses(username):
    db = get_mongo_db()
    if db is None:
        return None
    docs = list(db.expenses.find({"username": username}, {"_id": 0, "username": 0}))
    if not docs:
        return None
    df = pd.DataFrame(docs)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

# ══════════════════════════════════════════════════════════════════
# 3. EXPENSE PREDICTION (ML)
# ══════════════════════════════════════════════════════════════════
def predict_next_month(df):
    if not SKLEARN_OK or len(df) < 3:
        return None
    monthly = df.copy()
    monthly['Month'] = monthly['Date'].dt.to_period('M')
    monthly_sum = monthly.groupby('Month')['Amount'].sum().reset_index()
    monthly_sum['MonthNum'] = range(len(monthly_sum))
    if len(monthly_sum) < 2:
        return None
    X = monthly_sum[['MonthNum']].values
    y = monthly_sum['Amount'].values
    model = LinearRegression()
    model.fit(X, y)
    next_month_num = len(monthly_sum)
    prediction = model.predict([[next_month_num]])[0]
    return max(0, round(prediction))

# ══════════════════════════════════════════════════════════════════
# 4. RECEIPT SCANNER (OCR via Gemini Vision)
# ══════════════════════════════════════════════════════════════════
def scan_receipt_with_gemini(image_bytes, mime_type):
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except:
        return None, "⚠️ GEMINI_API_KEY not found"
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    b64 = base64.b64encode(image_bytes).decode()
    prompt = """You are a receipt OCR assistant. Extract ALL expense items from this receipt image.
    Return ONLY a JSON array like this (no markdown, no explanation):
    [{"description": "Item name", "amount": 250, "category": "Food"},...]
    Categories must be one of: Food, Transport, Shopping, Entertainment, Bills, Education, Health, Other.
    If you cannot read the receipt clearly, return an empty array: []"""
    data = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": b64}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {"maxOutputTokens": 500, "temperature": 0.1}
    }
    try:
        response = requests.post(url, json=data, timeout=20)
        if response.status_code == 200:
            raw = response.json()['candidates'][0]['content']['parts'][0]['text']
            raw = raw.strip().replace("```json", "").replace("```", "").strip()
            import json
            items = json.loads(raw)
            return items, None
        return None, f"⚠️ Error {response.status_code}"
    except Exception as e:
        return None, f"⚠️ Error: {str(e)}"

# ══════════════════════════════════════════════════════════════════
# 5. ANOMALY DETECTION
# ══════════════════════════════════════════════════════════════════
def detect_anomalies(df):
    anomalies = []
    if len(df) < 5:
        return anomalies
    for category in df['Category'].unique():
        cat_df = df[df['Category'] == category]['Amount']
        if len(cat_df) < 3:
            continue
        mean = cat_df.mean()
        std = cat_df.std()
        if std == 0:
            continue
        for _, row in df[df['Category'] == category].iterrows():
            z_score = (row['Amount'] - mean) / std
            if z_score > 2:
                anomalies.append({
                    'Date': row['Date'].strftime('%Y-%m-%d'),
                    'Category': category,
                    'Amount': row['Amount'],
                    'Avg': round(mean),
                    'ZScore': round(z_score, 2)
                })
    return anomalies

# ══════════════════════════════════════════════════════════════════
# 6. PDF REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════
def generate_pdf_report(df, budget, username="User"):
    if not REPORTLAB_OK:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#1a1a2e'))
    sub_style = ParagraphStyle('sub', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    head_style = ParagraphStyle('head', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#16213e'))

    story.append(Paragraph("💰 Finance Tracker — Monthly Report", title_style))
    story.append(Paragraph(f"Generated for: {username} | Date: {datetime.now().strftime('%d %B %Y')}", sub_style))
    story.append(Spacer(1, 0.2*inch))

    # Summary table
    total = df['Amount'].sum()
    remaining = budget - total
    days = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
    summary_data = [
        ["Metric", "Value"],
        ["Total Spent", f"Rs. {total:,.0f}"],
        ["Monthly Budget", f"Rs. {budget:,.0f}"],
        ["Remaining", f"Rs. {remaining:,.0f}"],
        ["Daily Average", f"Rs. {total/days:.0f}"],
        ["Total Transactions", str(len(df))],
        ["Categories Used", str(df['Category'].nunique())],
    ]
    t = Table(summary_data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#16213e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f8f9fa'), colors.white]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(Paragraph("📊 Summary", head_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))

    # Category breakdown
    story.append(Paragraph("📂 Category Breakdown", head_style))
    story.append(Spacer(1, 0.1*inch))
    cat_data = [["Category", "Amount (Rs.)", "% of Total", "Transactions"]]
    cat_summary = df.groupby('Category').agg(Amount=('Amount','sum'), Count=('Amount','count')).sort_values('Amount', ascending=False)
    for cat, row in cat_summary.iterrows():
        pct = row['Amount'] / total * 100
        cat_data.append([cat, f"{row['Amount']:,.0f}", f"{pct:.1f}%", str(row['Count'])])
    t2 = Table(cat_data, colWidths=[2*inch, 2*inch, 1.5*inch, 1.5*inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#e8f4f8'), colors.white]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.2*inch))

    # Recent transactions
    story.append(Paragraph("🧾 Recent Transactions (Last 10)", head_style))
    story.append(Spacer(1, 0.1*inch))
    recent = df.sort_values('Date', ascending=False).head(10)
    tx_data = [["Date", "Category", "Description", "Amount"]]
    for _, row in recent.iterrows():
        tx_data.append([
            row['Date'].strftime('%d-%m-%Y'),
            row['Category'],
            str(row['Description'])[:25],
            f"Rs. {row['Amount']:,.0f}"
        ])
    t3 = Table(tx_data, colWidths=[1.5*inch, 1.5*inch, 2.5*inch, 1.5*inch])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#533483')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f3e8ff'), colors.white]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Generated by AI Finance Tracker", sub_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

# ══════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════
db_available = get_mongo_db() is not None

if not st.session_state.logged_in:
    st.title("💰 AI Finance Tracker")
    st.markdown("### 🔐 Login / Register")

    if not db_available:
        st.warning("⚠️ MongoDB not connected — using Guest mode (data won't be saved across sessions). Add MONGO_URI to secrets to enable accounts.")
        if st.button("Continue as Guest 👤"):
            st.session_state.logged_in = True
            st.session_state.username = "Guest"
            st.rerun()
        st.stop()

    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])
    with tab1:
        with st.form("login_form"):
            lu = st.text_input("Username")
            lp = st.text_input("Password", type="password")
            if st.form_submit_button("Login", type="primary"):
                ok, msg = mongo_login(lu, lp)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.username = lu
                    loaded = mongo_load_expenses(lu)
                    if loaded is not None:
                        st.session_state.expenses = loaded
                    st.success(f"Welcome back, {lu}!")
                    st.rerun()
                else:
                    st.error(msg)
    with tab2:
        with st.form("register_form"):
            ru = st.text_input("Choose Username")
            rp = st.text_input("Choose Password", type="password")
            rp2 = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Register", type="primary"):
                if rp != rp2:
                    st.error("Passwords don't match!")
                elif len(ru) < 3:
                    st.error("Username must be at least 3 characters")
                else:
                    ok, msg = mongo_register(ru, rp)
                    if ok:
                        st.success("✅ Registered! Please login.")
                    else:
                        st.error(msg)
    st.stop()

# ══════════════════════════════════════════════════════════════════
# MAIN APP (after login)
# ══════════════════════════════════════════════════════════════════
st.title("💰 AI-Powered Finance Tracker")
st.markdown(f"Welcome, **{st.session_state.username}** 👋 | Track expenses and get AI insights!")
st.markdown("---")

# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("➕ Add New Expense")
    st.session_state.monthly_budget = st.number_input(
        "🎯 Monthly Budget (₹)",
        min_value=1000,
        value=st.session_state.monthly_budget,
        step=500
    )
    st.markdown("---")
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
            if db_available and st.session_state.username != "Guest":
                mongo_save_expenses(st.session_state.username, st.session_state.expenses)
            st.success(f"✅ Added: {exp_desc} - ₹{exp_amount}")
    st.markdown("---")
    if st.button("🗑️ Clear All Data"):
        st.session_state.expenses = pd.DataFrame(columns=['Date', 'Category', 'Amount', 'Description'])
        st.session_state.chat_history = []
        st.session_state.latest_response = None
        st.session_state.latest_question = None
        if db_available and st.session_state.username != "Guest":
            mongo_save_expenses(st.session_state.username, st.session_state.expenses)
        st.success("✅ All data cleared!")
    st.markdown("---")
    if st.button("🚪 Logout"):
        for key in ['logged_in', 'username', 'chat_history', 'latest_response', 'latest_question']:
            st.session_state[key] = None if 'response' in key or 'question' in key else False if key == 'logged_in' else ""
        st.session_state.chat_history = []
        st.rerun()

df = st.session_state.expenses

# ══════════════════════════════════════════════════════════════════
# SECTION: AI ADVISOR
# ══════════════════════════════════════════════════════════════════
st.subheader("🤖 Ask AI Financial Advisor")
st.markdown("Get personalized advice based on your spending!")

col1, col2 = st.columns([4, 1])
with col1:
    user_question = st.text_input("Ask about your finances:", placeholder="e.g., How can I save money? What's my biggest expense?", key="question_input")
with col2:
    ask_button = st.button("💬 Ask AI", type="primary")

if ask_button and user_question:
    with st.spinner("🤔 AI is analyzing..."):
        total = df['Amount'].sum()
        category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        top_category = category_totals.index[0]
        top_category_amount = category_totals.values[0]
        top_category_percentage = (top_category_amount / total * 100)
        recent_df = df.sort_values('Date', ascending=False).head(5)
        recent_text = ", ".join([f"{r['Category']}: ₹{r['Amount']}" for _, r in recent_df.iterrows()])
        days_tracked = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
        daily_avg = total / days_tracked
        category_list = ", ".join([f"{cat}: ₹{amt:.0f} ({amt/total*100:.0f}%)" for cat, amt in category_totals.items()])
        context = f"""You are a smart, friendly personal finance advisor for an Indian user.
        Analyze their real expense data and give specific, actionable advice.
        THEIR SPENDING DATA:
        - Total spent: ₹{total:,.0f} over {days_tracked} days
        - Daily average: ₹{daily_avg:.0f}/day
        - Monthly estimate: ₹{daily_avg * 30:,.0f}/month
        CATEGORY BREAKDOWN: {category_list}
        RECENT TRANSACTIONS: {recent_text}
        TOP SPENDING AREA: {top_category} at ₹{top_category_amount:.0f} ({top_category_percentage:.0f}% of total)
        INSTRUCTIONS:
        - Give specific advice using their EXACT numbers
        - If they ask for tips, give 3-4 numbered actionable tips with real ₹ amounts
        - Always end with one motivational next step
        - Use ₹ symbol for all amounts and emojis to make it readable"""
        ai_response = ask_ai(user_question, context)
        st.session_state.chat_history.append({'user': user_question, 'ai': ai_response})
        st.session_state.latest_response = ai_response
        st.session_state.latest_question = user_question
        st.rerun()

if st.session_state.latest_response:
    st.success(f"🤖 AI Response to: '{st.session_state.latest_question}'")
    st.info(st.session_state.latest_response)
    st.markdown("---")

if st.session_state.chat_history:
    with st.expander("💬 Chat History", expanded=False):
        for idx, chat in enumerate(reversed(st.session_state.chat_history[-5:]), 1):
            st.markdown(f"**Q{idx}:** {chat['user']}")
            st.info(chat['ai'])
            if idx < min(5, len(st.session_state.chat_history)):
                st.markdown("---")

st.markdown("---")

if len(df) > 0:
    # ── KEY METRICS ───────────────────────────────────────────────
    st.subheader("📈 Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)
    remaining_budget = st.session_state.monthly_budget - df['Amount'].sum()
    col1.metric("💵 Total Spent", f"₹{df['Amount'].sum():,.0f}")
    col2.metric("📊 Avg Transaction", f"₹{df['Amount'].mean():,.0f}")
    col3.metric("📈 Highest", f"₹{df['Amount'].max():,.0f}")
    col4.metric("🔢 Entries", len(df))
    col5.metric("🎯 Remaining", f"₹{remaining_budget:,.0f}")

    spent = df['Amount'].sum()
    usage = min(spent / st.session_state.monthly_budget, 1.0)
    st.write(f"💰 Budget Usage: ₹{spent:,.0f} / ₹{st.session_state.monthly_budget:,.0f}")
    st.progress(usage)
    if spent > st.session_state.monthly_budget:
        st.error("🚨 Budget Exceeded!")
    elif spent > st.session_state.monthly_budget * 0.8:
        st.warning("⚠️ More than 80% of budget used")
    else:
        st.success("✅ Budget under control")

    st.markdown("---")

    # ── CHARTS ────────────────────────────────────────────────────
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

    # ── CATEGORY SUMMARY ──────────────────────────────────────────
    st.subheader("💰 Category Summary")
    category_summary = df.groupby('Category')['Amount'].sum().reset_index()
    category_summary['Percentage'] = (category_summary['Amount'] / category_summary['Amount'].sum() * 100).round(1)
    category_summary = category_summary.sort_values('Amount', ascending=False)
    st.dataframe(category_summary, hide_index=True, use_container_width=True)

    st.markdown("---")

    # ── EXPENSE PREDICTION (ML) ───────────────────────────────────
    st.subheader("🤖 Expense Prediction (ML)")
    if not SKLEARN_OK:
        st.info("📦 Install scikit-learn to enable predictions: `pip install scikit-learn`")
    else:
        predicted = predict_next_month(df)
        if predicted is None:
            st.info("📊 Add expenses across at least 2 months to get predictions.")
        else:
            col1, col2, col3 = st.columns(3)
            days_left = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
            daily_avg_pred = df['Amount'].sum() / days_left
            col1.metric("📅 Predicted Next Month", f"₹{predicted:,.0f}")
            col2.metric("📉 Daily Average", f"₹{daily_avg_pred:.0f}")
            col3.metric("💡 Budget Gap", f"₹{st.session_state.monthly_budget - predicted:,.0f}")
            if predicted > st.session_state.monthly_budget:
                st.error(f"🚨 ML predicts you'll exceed budget by ₹{predicted - st.session_state.monthly_budget:,.0f} next month!")
            else:
                st.success(f"✅ ML predicts you'll stay within budget next month. Good job!")

            monthly_chart = df.copy()
            monthly_chart['Month'] = monthly_chart['Date'].dt.to_period('M').astype(str)
            monthly_chart = monthly_chart.groupby('Month')['Amount'].sum().reset_index()
            st.line_chart(monthly_chart.set_index('Month'))

    st.markdown("---")

    # ── RECEIPT SCANNER ───────────────────────────────────────────
    st.subheader("📷 Receipt Scanner")
    st.markdown("Upload a bill/receipt image — AI will auto-extract and add expenses!")
    uploaded_receipt = st.file_uploader("Upload Receipt Image", type=["jpg", "jpeg", "png", "webp"], key="receipt_uploader")
    if uploaded_receipt is not None:
        st.image(uploaded_receipt, caption="Uploaded Receipt", width=300)
        if st.button("🔍 Scan & Extract Expenses", type="primary"):
            with st.spinner("🤖 AI is reading your receipt..."):
                image_bytes = uploaded_receipt.read()
                mime_type = uploaded_receipt.type
                items, error = scan_receipt_with_gemini(image_bytes, mime_type)
                if error:
                    st.error(error)
                elif not items:
                    st.warning("⚠️ Could not extract any items. Try a clearer image.")
                else:
                    st.success(f"✅ Found {len(items)} item(s)!")
                    preview_df = pd.DataFrame(items)
                    st.dataframe(preview_df, hide_index=True, use_container_width=True)
                    new_rows = []
                    for item in items:
                        new_rows.append({
                            'Date': pd.to_datetime(datetime.now().date()),
                            'Category': item.get('category', 'Other'),
                            'Amount': float(item.get('amount', 0)),
                            'Description': item.get('description', '')
                        })
                    if new_rows:
                        new_df = pd.DataFrame(new_rows)
                        st.session_state.expenses = pd.concat([st.session_state.expenses, new_df], ignore_index=True)
                        if db_available and st.session_state.username != "Guest":
                            mongo_save_expenses(st.session_state.username, st.session_state.expenses)
                        st.success(f"✅ {len(new_rows)} expense(s) added automatically!")
                        st.rerun()

    st.markdown("---")

    # ── ANOMALY DETECTION ─────────────────────────────────────────
    st.subheader("🚨 AI Anomaly Detection")
    anomalies = detect_anomalies(df)
    if not anomalies:
        st.success("✅ No unusual expenses detected. Spending looks normal!")
    else:
        st.error(f"⚠️ {len(anomalies)} unusual expense(s) detected!")
        for a in anomalies:
            st.warning(
                f"🚨 **{a['Category']}** on {a['Date']} — ₹{a['Amount']:,.0f} "
                f"(your avg is ₹{a['Avg']:,.0f}, this is {a['ZScore']}x higher than normal)"
            )

    st.markdown("---")

    # ── SMART ALERTS ──────────────────────────────────────────────
    st.subheader("🔔 Smart Alerts")
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
        alerts.append(("info", f"💡 {top_category} is {percentage:.1f}% of your spending"))

    days = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
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

    # ── ALL TRANSACTIONS ──────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 All Transactions")
    with col2:
        csv = df.to_csv(index=False)
        st.download_button("📥 CSV", csv, "expenses.csv", "text/csv")

    display_df = df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df.sort_values('Date', ascending=False), hide_index=True, use_container_width=True)

    st.markdown("---")

    # ── STATISTICS ────────────────────────────────────────────────
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

    st.markdown("---")

    # ── PDF REPORT ────────────────────────────────────────────────
    st.subheader("📄 Monthly PDF Report")
    if not REPORTLAB_OK:
        st.info("📦 Install reportlab to enable PDF reports: `pip install reportlab`")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("Download a full report with charts, category breakdown, and AI recommendations.")
        with col2:
            pdf_bytes = generate_pdf_report(df, st.session_state.monthly_budget, st.session_state.username)
            if pdf_bytes:
                month_name = datetime.now().strftime("%B_%Y")
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name=f"Finance_Report_{month_name}.pdf",
                    mime="application/pdf",
                    type="primary"
                )

else:
    st.info("👋 Add your first expense using the sidebar!")

st.markdown("---")
st.caption("💰 AI Finance Tracker • Powered by Gemini AI • Built with ❤️")
