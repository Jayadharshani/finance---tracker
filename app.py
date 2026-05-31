import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import base64
import io
import json

# ── Optional imports ──────────────────────────────────────────────
try:
    from sklearn.linear_model import LinearRegression
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

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
# 2. EXPENSE PREDICTION (ML)
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
    prediction = model.predict([[len(monthly_sum)]])[0]
    return max(0, round(prediction))

# ══════════════════════════════════════════════════════════════════
# 3. RECEIPT SCANNER (Gemini Vision)
# ══════════════════════════════════════════════════════════════════
def scan_receipt_with_gemini(image_bytes, mime_type):
    try:
        API_KEY = st.secrets["GEMINI_API_KEY"]
    except:
        return None, "⚠️ GEMINI_API_KEY not found"
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    b64 = base64.b64encode(image_bytes).decode()
    prompt = """Look at this receipt image and extract all items/expenses.

You MUST respond with ONLY a valid JSON array. No explanation, no markdown, no extra text.
Each object must have exactly these 3 keys: description, amount, category.
Amount must be a number (no currency symbols).
Category must be one of: Food, Transport, Shopping, Entertainment, Bills, Education, Health, Other.

Example of valid response:
[{"description":"Coffee","amount":80,"category":"Food"},{"description":"Bus ticket","amount":30,"category":"Transport"}]

If the image is not a receipt or unreadable, respond with exactly: []

IMPORTANT: Return raw JSON only. No ```json``` tags. No newlines inside strings."""

    data = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime_type, "data": b64}},
            {"text": prompt}
        ]}],
        "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.0}
    }
    try:
        response = requests.post(url, json=data, timeout=20)
        if response.status_code != 200:
            return None, f"⚠️ API Error {response.status_code}: {response.text[:200]}"

        raw = response.json()['candidates'][0]['content']['parts'][0]['text']

        # Clean up common Gemini response issues
        raw = raw.strip()
        raw = raw.replace("```json", "").replace("```JSON", "").replace("```", "")
        raw = raw.strip()

        # Extract just the JSON array if extra text exists
        start = raw.find('[')
        end   = raw.rfind(']')
        if start != -1 and end != -1:
            raw = raw[start:end+1]
        else:
            return None, f"⚠️ Could not find JSON array in response. AI said: {raw[:300]}"

        # Fix common JSON issues: single quotes → double quotes
        raw = raw.replace("'", '"')

        # Remove trailing commas before ] or }
        import re
        raw = re.sub(r',\s*([}\]])', r'\1', raw)

        items = json.loads(raw)

        # Validate and clean each item
        cleaned = []
        valid_categories = ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Education", "Health", "Other"]
        for item in items:
            if not isinstance(item, dict):
                continue
            desc   = str(item.get('description') or item.get('name') or item.get('item') or 'Unknown')
            amt    = item.get('amount') or item.get('price') or item.get('cost') or 0
            cat    = item.get('category') or 'Other'
            try:
                amt = float(str(amt).replace('₹','').replace(',','').replace('Rs','').strip())
            except:
                amt = 0.0
            if cat not in valid_categories:
                cat = 'Other'
            if amt > 0:
                cleaned.append({'description': desc, 'amount': amt, 'category': cat})

        return cleaned, None

    except json.JSONDecodeError as e:
        return None, f"⚠️ JSON parse error: {str(e)} | Raw response: {raw[:300]}"
    except Exception as e:
        return None, f"⚠️ Error: {str(e)}"

# ══════════════════════════════════════════════════════════════════
# 4. ANOMALY DETECTION
# ══════════════════════════════════════════════════════════════════
def detect_anomalies(df):
    anomalies = []
    if len(df) < 5:
        return anomalies
    for category in df['Category'].unique():
        cat_amounts = df[df['Category'] == category]['Amount']
        if len(cat_amounts) < 3:
            continue
        mean = cat_amounts.mean()
        std = cat_amounts.std()
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
# 5. PDF REPORT
# ══════════════════════════════════════════════════════════════════
def generate_pdf_report(df, budget):
    if not REPORTLAB_OK:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#1a1a2e'))
    sub_style   = ParagraphStyle('sub',   parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    head_style  = ParagraphStyle('head',  parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#16213e'))

    story.append(Paragraph("💰 Finance Tracker — Monthly Report", title_style))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}", sub_style))
    story.append(Spacer(1, 0.2*inch))

    total    = df['Amount'].sum()
    remaining = budget - total
    days     = max((df['Date'].max() - df['Date'].min()).days + 1, 1)

    summary_data = [
        ["Metric", "Value"],
        ["Total Spent",       f"Rs. {total:,.0f}"],
        ["Monthly Budget",    f"Rs. {budget:,.0f}"],
        ["Remaining",         f"Rs. {remaining:,.0f}"],
        ["Daily Average",     f"Rs. {total/days:.0f}"],
        ["Total Transactions",str(len(df))],
        ["Categories Used",   str(df['Category'].nunique())],
    ]
    t = Table(summary_data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#16213e')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f8f9fa'), colors.white]),
        ('GRID',   (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE',(0,0), (-1,-1), 10),
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
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#e8f4f8'), colors.white]),
        ('GRID',   (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE',(0,0), (-1,-1), 10),
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
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f3e8ff'), colors.white]),
        ('GRID',   (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE',(0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Generated by AI Finance Tracker", sub_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

# ══════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════
st.title("💰 AI-Powered Finance Tracker")
st.markdown("Track expenses and get AI-powered insights!")
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
        exp_date     = st.date_input("Date", datetime.now())
        exp_category = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Education", "Health", "Other"])
        amount_method = st.radio("Amount input:", ["Quick Select", "Type Exact"], horizontal=True, label_visibility="collapsed")
        if amount_method == "Quick Select":
            exp_amount = st.select_slider("Amount (₹)", options=[50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000], value=100)
        else:
            exp_amount = st.number_input("Amount (₹)", min_value=0, value=100, step=1)
        exp_desc = st.text_input("Description")
        if st.form_submit_button("Add Expense"):
            new_row = pd.DataFrame({
                'Date':        [pd.to_datetime(exp_date)],
                'Category':    [exp_category],
                'Amount':      [exp_amount],
                'Description': [exp_desc]
            })
            st.session_state.expenses = pd.concat([st.session_state.expenses, new_row], ignore_index=True)
            st.success(f"✅ Added: {exp_desc} - ₹{exp_amount}")
    st.markdown("---")
    if st.button("🗑️ Clear All Data"):
        st.session_state.expenses = pd.DataFrame(columns=['Date', 'Category', 'Amount', 'Description'])
        st.session_state.chat_history   = []
        st.session_state.latest_response = None
        st.session_state.latest_question = None
        st.success("✅ All data cleared!")

df = st.session_state.expenses

# ══════════════════════════════════════════════════════════════════
# AI ADVISOR
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
        total           = df['Amount'].sum()
        category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        top_category    = category_totals.index[0]
        top_amt         = category_totals.values[0]
        top_pct         = (top_amt / total * 100)
        days_tracked    = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
        daily_avg       = total / days_tracked
        monthly_budget  = st.session_state.monthly_budget
        remaining       = monthly_budget - total

        # Full category breakdown as numbered list
        cat_lines = "\n".join([
            f"  {i+1}. {cat}: ₹{amt:,.0f} ({amt/total*100:.1f}%)"
            for i, (cat, amt) in enumerate(category_totals.items())
        ])

        # All transactions as a table string
        tx_lines = "\n".join([
            f"  {row['Date'].strftime('%d-%b')}: {row['Category']} | {row['Description']} | ₹{row['Amount']:,.0f}"
            for _, row in df.sort_values('Date', ascending=False).iterrows()
        ])

        # Single transaction max
        max_tx = df.loc[df['Amount'].idxmax()]
        min_tx = df.loc[df['Amount'].idxmin()]

        context = f"""You are a strict personal finance data analyst for an Indian user.
You have access to their EXACT expense data. ONLY answer based on this data. NEVER say "I don't have enough data" or give generic advice. Always use the EXACT numbers below.

=== USER EXPENSE DATA ===
Monthly Budget: ₹{monthly_budget:,.0f}
Total Spent: ₹{total:,.0f}
Remaining Budget: ₹{remaining:,.0f}
Days Tracked: {days_tracked}
Daily Average: ₹{daily_avg:.0f}/day
Projected Monthly Spend: ₹{daily_avg*30:,.0f}
Total Transactions: {len(df)}

=== CATEGORY-WISE SPENDING (Highest to Lowest) ===
{cat_lines}

=== HIGHEST SINGLE EXPENSE ===
  Category: {max_tx['Category']} | Description: {max_tx['Description']} | Amount: ₹{max_tx['Amount']:,.0f} | Date: {max_tx['Date'].strftime('%d-%b-%Y')}

=== LOWEST SINGLE EXPENSE ===
  Category: {min_tx['Category']} | Description: {min_tx['Description']} | Amount: ₹{min_tx['Amount']:,.0f} | Date: {min_tx['Date'].strftime('%d-%b-%Y')}

=== ALL TRANSACTIONS (Recent First) ===
{tx_lines}

=== STRICT RULES FOR YOUR RESPONSE ===
- NEVER start with greetings like "Hey!", "Hi!", "Thanks for reaching out"
- NEVER say "I don't have data" — the full data is given above
- ALWAYS start your answer directly with the facts from the data
- Use EXACT ₹ numbers from the data in every sentence
- If asked about highest spending: state the category name and exact amount immediately
- If asked for tips: give numbered tips with real ₹ savings amounts
- Keep response under 150 words, precise and to the point
- Use emojis only to highlight numbers, not as filler"""

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
    col1.metric("💵 Total Spent",      f"₹{df['Amount'].sum():,.0f}")
    col2.metric("📊 Avg Transaction",  f"₹{df['Amount'].mean():,.0f}")
    col3.metric("📈 Highest",          f"₹{df['Amount'].max():,.0f}")
    col4.metric("🔢 Entries",          len(df))
    col5.metric("🎯 Remaining",        f"₹{remaining_budget:,.0f}")

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
        st.bar_chart(df.groupby('Category')['Amount'].sum().sort_values(ascending=False))
    with col2:
        st.subheader("📈 Daily Trend")
        st.line_chart(df.groupby('Date')['Amount'].sum())

    st.markdown("---")

    # ── CATEGORY SUMMARY ──────────────────────────────────────────
    st.subheader("💰 Category Summary")
    cat_sum = df.groupby('Category')['Amount'].sum().reset_index()
    cat_sum['Percentage'] = (cat_sum['Amount'] / cat_sum['Amount'].sum() * 100).round(1)
    st.dataframe(cat_sum.sort_values('Amount', ascending=False), hide_index=True, use_container_width=True)

    st.markdown("---")

    # ── EXPENSE PREDICTION (ML) ───────────────────────────────────
    st.subheader("🤖 Expense Prediction (ML)")
    if not SKLEARN_OK:
        st.info("📦 Add `scikit-learn` to requirements.txt to enable predictions")
    else:
        predicted = predict_next_month(df)
        if predicted is None:
            st.info("📊 Add expenses across at least 2 months to get predictions.")
        else:
            col1, col2, col3 = st.columns(3)
            days_left    = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
            daily_avg_p  = df['Amount'].sum() / days_left
            col1.metric("📅 Predicted Next Month", f"₹{predicted:,.0f}")
            col2.metric("📉 Daily Average",         f"₹{daily_avg_p:.0f}")
            col3.metric("💡 Budget Gap",             f"₹{st.session_state.monthly_budget - predicted:,.0f}")
            if predicted > st.session_state.monthly_budget:
                st.error(f"🚨 ML predicts you'll exceed budget by ₹{predicted - st.session_state.monthly_budget:,.0f} next month!")
            else:
                st.success("✅ ML predicts you'll stay within budget next month. Good job!")
            monthly_chart = df.copy()
            monthly_chart['Month'] = monthly_chart['Date'].dt.to_period('M').astype(str)
            st.line_chart(monthly_chart.groupby('Month')['Amount'].sum())

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
                items, error = scan_receipt_with_gemini(image_bytes, uploaded_receipt.type)
                if error:
                    st.error(error)
                elif not items:
                    st.warning("⚠️ Could not extract any items. Try a clearer image.")
                else:
                    st.success(f"✅ Found {len(items)} item(s)!")
                    st.dataframe(pd.DataFrame(items), hide_index=True, use_container_width=True)
                    new_rows = [{'Date': pd.to_datetime(datetime.now().date()), 'Category': i.get('category', 'Other'), 'Amount': float(i.get('amount', 0)), 'Description': i.get('description', '')} for i in items]
                    st.session_state.expenses = pd.concat([st.session_state.expenses, pd.DataFrame(new_rows)], ignore_index=True)
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
            st.warning(f"🚨 **{a['Category']}** on {a['Date']} — ₹{a['Amount']:,.0f} (your avg is ₹{a['Avg']:,.0f}, this is {a['ZScore']}x higher than normal)")

    st.markdown("---")

    # ── SMART ALERTS ──────────────────────────────────────────────
    st.subheader("🔔 Smart Alerts")
    alerts = []
    category_totals = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
    if len(df) >= 7:
        df_sorted   = df.sort_values('Date')
        recent_week = df_sorted.tail(7)['Amount'].sum()
        if len(df) >= 14:
            prev_week = df_sorted.iloc[-14:-7]['Amount'].sum()
            if prev_week > 0:
                change = ((recent_week - prev_week) / prev_week) * 100
                if change > 20:
                    alerts.append(("warning", f"🚨 Spending UP {change:.1f}% this week!"))
                elif change < -20:
                    alerts.append(("success", f"✅ Spending DOWN {abs(change):.1f}% this week!"))
    top_cat = category_totals.index[0]
    top_amt = category_totals.values[0]
    pct     = (top_amt / df['Amount'].sum()) * 100
    if pct > 35:
        alerts.append(("info", f"💡 {top_cat} is {pct:.1f}% of your spending"))
    days      = max((df['Date'].max() - df['Date'].min()).days + 1, 1)
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
        st.download_button("📥 CSV", df.to_csv(index=False), "expenses.csv", "text/csv")
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
        st.info("📦 Add `reportlab` to requirements.txt to enable PDF reports")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("Download a full report with summary, category breakdown & recent transactions.")
        with col2:
            pdf_bytes = generate_pdf_report(df, st.session_state.monthly_budget)
            if pdf_bytes:
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name=f"Finance_Report_{datetime.now().strftime('%B_%Y')}.pdf",
                    mime="application/pdf",
                    type="primary"
                )

else:
    st.info("👋 Add your first expense using the sidebar!")

st.markdown("---")
st.caption("💰 AI Finance Tracker • Powered by Gemini AI • Built with ❤️")
