import streamlit as st
import requests
import time

# --- Configuration ---
try:
    API_KEY = st.secrets["QUICKFS_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("🚨 API Key missing! Please add `QUICKFS_API_KEY` to your `.streamlit/secrets.toml` file.")
    st.stop()

STOCKS = {
    "DNP (Warsaw)": "DNP:PL",
    "Ashtead Group (London)": "AHT:LN",
    "APi Group (USA)": "APG:US"
}

# --- Session State for Dark Mode ---
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

def toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

# --- Dynamic CSS ---
def local_css(is_dark):
    if is_dark:
        bg_color = "#0e1117"
        text_color = "#fafafa"
        card_bg = "#262730"
        border_color = "rgba(250, 250, 250, 0.1)"
        shadow_color = "rgba(0, 0, 0, 0.3)"
        label_color = "#d0d0d0"
        desc_color = "#b0b0b0"
    else:
        bg_color = "#ffffff"
        text_color = "#000000"
        card_bg = "#ffffff"
        border_color = "rgba(128, 128, 128, 0.1)"
        shadow_color = "rgba(0, 0, 0, 0.05)"
        label_color = "#5f6368"
        desc_color = "#70757a"

    st.markdown(f"""
    <style>
        .stApp {{ background-color: {bg_color}; color: {text_color}; }}
        html, body, [class*="css"] {{ font-family: 'Inter', 'Roboto', sans-serif; font-size: 1rem; color: {text_color}; }}
        
        div.metric-card {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px {shadow_color};
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        div.metric-card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 15px {shadow_color}; }}

        h4.metric-label {{
            font-size: 0.9rem;
            font-weight: 600;
            color: {label_color};
            opacity: 0.9;
            margin: 0 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        div.metric-value {{ font-size: 2.2rem; font-weight: 700; color: {text_color}; margin-bottom: 16px; }}

        div.metric-desc {{
            font-size: 0.9rem;
            line-height: 1.5;
            color: {desc_color};
            margin: 0;
            border-top: 1px solid {border_color};
            padding-top: 12px;
        }}
        div.metric-desc ul {{ padding-left: 20px; margin: 0; }}
        div.metric-desc li {{ margin-bottom: 6px; }}

        /* Streamlit overrides */
        h1, h2, h3, h4, h5, h6, .stMarkdown, .stText {{ color: {text_color} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- Robust Data Fetching ---
def fetch_quickfs_data(ticker, api_key, retries=2):
    url = f"https://public-api.quickfs.net/v1/data/all-data/{ticker}?api_key={api_key}"
    for attempt in range(retries + 1):
        try:
            response = requests.get(url)
            if response.status_code == 200: return response.json()
            elif response.status_code >= 500:
                if attempt < retries: time.sleep(1); continue
                else: st.error(f"❌ QuickFS Server Error (500) for {ticker}. API temporarily down."); return None
            else: st.error(f"❌ Error {response.status_code}: {response.reason}"); return None
        except requests.exceptions.RequestException as e: st.error(f"🚨 Connection Error: {e}"); return None
    return None

def extract_ttm_metric(data, metric_key):
    try:
        financials = data.get("data", {}).get("financials", {})
        keys_to_check = [metric_key] if isinstance(metric_key, str) else metric_key
        
        # 1. Explicit TTM
        for key in keys_to_check:
            if "ttm" in financials and key in financials["ttm"]: return financials["ttm"][key]
        
        # 2. Quarterly Sum Fallback
        quarterly = financials.get("quarterly", {})
        for key in keys_to_check:
            if key in quarterly:
                values = quarterly[key]
                if values and len(values) >= 4:
                    valid_values = [v for v in values if v is not None]
                    if len(valid_values) >= 4: return sum(valid_values[-4:])
        return None
    except Exception: return None

def format_currency(value, currency_symbol="$"):
    if value is None: return "N/A"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000: return f"{currency_symbol}{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{currency_symbol}{value / 1_000_000:.2f}M"
    else: return f"{currency_symbol}{value:,.2f}"

def render_card(label, value_str, description_html, accent_color="#4285F4"):
    html = f"""
    <div class="metric-card" style="border-top: 4px solid {accent_color};">
        <div><h4 class="metric-label">{label}</h4><div class="metric-value">{value_str}</div></div>
        <div class="metric-desc">{description_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- Main App ---
st.set_page_config(page_title="Financial Dashboard", layout="wide")

with st.sidebar:
    st.header("Search")
    selected_stock_name = st.selectbox("Select Stock", list(STOCKS.keys()))
    selected_ticker = STOCKS[selected_stock_name]
    st.markdown("---")
    st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, on_change=toggle_dark_mode)
    st.markdown("---")
    st.caption("Data source: **QuickFS API**")

local_css(st.session_state.dark_mode)

json_data = fetch_quickfs_data(selected_ticker, API_KEY)

if json_data:
    meta = json_data.get("data", {}).get("metadata", {})
    currency = meta.get("currency", "USD")
    curr_sym = "$" if currency == "USD" else (currency + " ")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"{selected_stock_name}")
        st.markdown(f"#### Ticker: **{selected_ticker}**")
    st.divider()

    # Data Extraction
    rev = extract_ttm_metric(json_data, "revenue")
    gp = extract_ttm_metric(json_data, "gross_profit")
    op = extract_ttm_metric(json_data, "operating_income")
    ebitda = extract_ttm_metric(json_data, "ebitda")
    ni = extract_ttm_metric(json_data, "net_income")
    eps = extract_ttm_metric(json_data, "eps_diluted")
    
    tax = extract_ttm_metric(json_data, "income_tax")
    nopat = (op - tax) if (op is not None and tax is not None) else (op * (1 - 0.21) if op else None)
    
    ocf = extract_ttm_metric(json_data, ["cf_cfo", "cfo"]) 
    fcf = extract_ttm_metric(json_data, "fcf")

    # --- Explanations (Restored Detail) ---
    desc_revenue = """
    <ul>
        <li>Top-line sales indicating market demand for the product or service.</li>
        <li>Reflects the sheer scale of operations.</li>
    </ul>
    """
    
    desc_gp = """
    <ul>
        <li>Revenue minus Cost of Goods Sold (COGS). Measures production efficiency.</li>
        <li>Negative values imply the company loses money on every unit before covering overhead.</li>
        <li>COGS includes raw materials, manufacturing costs, and depreciation on production assets.</li>
    </ul>
    """
    
    desc_op = """
    <ul>
        <li>Gross Profit minus operating expenses (Marketing, G&A, R&D).</li>
        <li>G&A covers indirect costs (rent, admin salaries); R&D covers product improvement.</li>
        <li>Shows core business profitability excluding taxes and financing decisions.</li>
    </ul>
    """
    
    desc_ebitda = """
    <ul>
        <li>Earnings Before Interest, Taxes, Depreciation, and Amortization.</li>
        <li>Proxy for cash flow; removes non-cash charges like depreciation.</li>
        <li>Popular for valuing tech and infrastructure as it focuses on operational cash generation.</li>
    </ul>
    """
    
    desc_nopat = """
    <ul>
        <li>Net Operating Profit After Tax. Formula: <i>EBIT × (1 − Tax Rate)</i>.</li>
        <li>Shows potential cash earnings if the company were debt-free.</li>
        <li>Crucial for ROIC analysis and comparing companies with different leverage (debt levels).</li>
    </ul>
    """
    
    desc_ni = """
    <ul>
        <li>"Bottom Line" profit for shareholders after <i>all</i> expenses (suppliers, employees, interest, taxes).</li>
        <li>The official earnings figure used for P/E ratios.</li>
        <li>Unlike EBIT, this is heavily influenced by interest costs.</li>
    </ul>
    """
    
    desc_eps = """
    <ul>
        <li>Net Income divided by current shares outstanding.</li>
        <li>Shows exactly how much of today's profit is allocated to each share you own.</li>
    </ul>
    """
    
    desc_ocf = """
    <ul>
        <li>Cash actually generated from day-to-day operations.</li>
        <li>Adjusts Net Income for non-cash items and working capital changes.</li>
        <li>Sales on credit increase Net Income but do not increase OCF until collected.</li>
    </ul>
    """
    
    desc_fcf = """
    <ul>
        <li>Cash remaining after operating costs and necessary CapEx.</li>
        <li>Represents "truly free" money for dividends, buybacks, or reinvestment.</li>
        <li>Shows cash left for shareholders after servicing debt and maintaining assets.</li>
    </ul>
    """

    # --- Layout ---
    st.subheader("📊 Income Statement")
    c_inc = "#3b82f6"
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("1. Revenue (Sales) — Top-Line", format_currency(rev, curr_sym), desc_revenue, c_inc)
    with c2: render_card("2. Gross Profit (Production Efficiency)", format_currency(gp, curr_sym), desc_gp, c_inc)
    with c3: render_card("3. Operating Profit / EBIT (Profitability)", format_currency(op, curr_sym), desc_op, c_inc)
    with c4: render_card("4. EBITDA (Operating Profit)", format_currency(ebitda, curr_sym), desc_ebitda, c_inc)
    
    st.markdown(" ") 
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("5. NOPAT (After-Tax Operating Profit)", format_currency(nopat, curr_sym), desc_nopat, c_inc)
    with c2: render_card("6. Net Income (Earnings) — Bottom-Line", format_currency(ni, curr_sym), desc_ni, c_inc)
    with c3: render_card("7. Earnings Per Share (EPS)", f"{curr_sym}{eps:.2f}" if eps else "N/A", desc_eps, c_inc)
    with c4: st.empty() 

    st.markdown("---")

    st.subheader("💸 Cash Flow")
    c_cf = "#10b981"
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("8. Operating Cash Flow", format_currency(ocf, curr_sym), desc_ocf, c_cf)
    with c2: render_card("9. Free Cash Flow (Truly Free Money)", format_currency(fcf, curr_sym), desc_fcf, c_cf)
    with c3: st.empty()
    with c4: st.empty()
