import streamlit as st
import requests
import pandas as pd
import time

# --- Configuration ---
try:
    API_KEY = st.secrets["QUICKFS_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("🚨 API Key missing! Please add `QUICKFS_API_KEY` to your `.streamlit/secrets.toml` file.")
    st.stop()

# Preset examples for quick selection
EXAMPLE_STOCKS = {
    "DNP (Warsaw)": "DNP:PL",
    "Ashtead Group (London)": "AHT:LN",
    "APi Group (USA)": "APG:US"
}

# --- Session State for Dark Mode ---
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

def toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

# --- Dynamic CSS for Material Design ---
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
            font-size: 0.95rem;
            line-height: 1.5;
            color: {desc_color};
            margin: 0;
            border-top: 1px solid {border_color};
            padding-top: 12px;
        }}
        
        .stAlert {{ border-radius: 8px; }}
        h1, h2, h3, h4, h5, h6, .stMarkdown, .stText, .stRadio label {{ color: {text_color} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- Data Fetching ---
def fetch_quickfs_data(ticker, api_key, retries=2):
    url = f"https://public-api.quickfs.net/v1/data/all-data/{ticker}?api_key={api_key}"
    for attempt in range(retries + 1):
        try:
            response = requests.get(url)
            if response.status_code == 200: return response.json()
            elif response.status_code >= 500:
                if attempt < retries: time.sleep(1); continue
                else: st.error(f"❌ QuickFS Server Error (500) for {ticker}. The API is temporarily down for this stock."); return None
            elif response.status_code == 404:
                st.error(f"❌ Ticker '{ticker}' not found. Please check format (e.g. AAPL:US)."); return None
            else: st.error(f"❌ Error {response.status_code}: {response.reason} for {ticker}"); return None
        except requests.exceptions.RequestException as e: st.error(f"🚨 Connection Error: {e}"); return None
    return None

def extract_historical_df(data, years=10):
    """
    Extracts last 10 years + TTM into a clean DataFrame for the 'View Data' module.
    """
    try:
        fin = data.get("data", {}).get("financials", {})
        annual = fin.get("annual", {})
        ttm = fin.get("ttm", {})
        
        # Get Fiscal Years (e.g. 2014, 2015...)
        dates = data.get("data", {}).get("metadata", {}).get("period_end_date", [])
        years_list = [d.split("-")[0] for d in dates]

        # Metric Config: Label -> [Key candidates]
        metrics_map = {
            "Revenue": ["revenue"],
            "Gross Profit": ["gross_profit"],
            "Operating Profit": ["operating_income"],
            "EBITDA": ["ebitda"],
            "NOPAT": ["nopat_derived"], # Calc handled below
            "Net Income": ["net_income"],
            "EPS (Diluted)": ["eps_diluted"],
            "Operating Cash Flow": ["cf_cfo", "cfo"],
            "Free Cash Flow": ["fcf"]
        }

        history_data = {}

        # 1. Helper to get TTM value
        def get_ttm(keys):
            for k in keys:
                if "ttm" in fin and k in fin["ttm"]: return fin["ttm"][k]
            # Fallback sum last 4 qtrs
            q = fin.get("quarterly", {})
            for k in keys:
                if k in q and q[k]:
                     valid = [x for x in q[k] if x is not None]
                     if len(valid) >= 4: return sum(valid[-4:])
            return None

        # 2. Build rows
        for label, keys in metrics_map.items():
            row_data = []
            
            # TTM Column
            ttm_val = get_ttm(keys)
            
            # Manual NOPAT TTM fallback
            if label == "NOPAT" and ttm_val is None:
                op = get_ttm(["operating_income"])
                tax = get_ttm(["income_tax"])
                if op is not None:
                     ttm_val = (op - tax) if tax is not None else (op * 0.79)
            
            row_data.append(ttm_val)

            # History Columns
            valid_key = next((k for k in keys if k in annual), None)
            
            if valid_key:
                annual_vals = annual[valid_key]
                # Manual NOPAT History fallback
                if label == "NOPAT" and not valid_key:
                    op_hist = annual.get("operating_income", [])
                    tax_hist = annual.get("income_tax", [])
                    annual_vals = []
                    for i in range(len(op_hist)):
                        try: annual_vals.append((op_hist[i] or 0) - (tax_hist[i] or 0))
                        except: annual_vals.append(None)

                # Slice last N years
                sliced_vals = annual_vals[-years:]
                sliced_vals.reverse() # Newest first for table
                row_data.extend(sliced_vals)
            else:
                row_data.extend([None] * years)
                
            history_data[label] = row_data

        # Columns: TTM, 2023, 2022...
        cols = ["TTM"]
        rev_years = years_list[-years:]
        rev_years.reverse()
        cols.extend(rev_years)

        # Pad rows to match columns length if history is short
        final_data = {}
        for k, v in history_data.items():
            if len(v) < len(cols): v.extend([None]*(len(cols)-len(v)))
            final_data[k] = v[:len(cols)]

        df = pd.DataFrame(final_data, index=cols).T
        return df
    except Exception as e:
        return pd.DataFrame()

def format_currency(value, currency_symbol="$"):
    if value is None: return "N/A"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000: return f"{currency_symbol}{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000: return f"{currency_symbol}{value / 1_000_000:.2f}M"
    else: return f"{currency_symbol}{value:,.2f}"

def render_card(label, value_str, description, accent_color="#4285F4"):
    html = f"""
    <div class="metric-card" style="border-top: 4px solid {accent_color};">
        <div>
            <h4 class="metric-label">{label}</h4>
            <div class="metric-value">{value_str}</div>
        </div>
        <p class="metric-desc">{description}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- Main App ---
st.set_page_config(page_title="Financial Dashboard", layout="wide")

with st.sidebar:
    st.header("Search")
    
    # (1) Ticker Search Logic
    search_input = st.text_input("Enter Ticker (e.g. AAPL:US)", value="")
    st.markdown("**Quick Select:**")
    selected_example = st.selectbox("Choose Example", ["(Custom Search)"] + list(EXAMPLE_STOCKS.keys()))
    
    if search_input: target_ticker = search_input.strip()
    elif selected_example != "(Custom Search)": target_ticker = EXAMPLE_STOCKS[selected_example]
    else: target_ticker = "DNP:PL" # Default

    st.markdown("---")
    
    # (2) Filter: 10 Years Back
    st.subheader("Time Period")
    # A slider to control how far back we look (visual control) or a simple toggle
    # Since prompt asked to filter/sort, a selectbox is clean.
    selected_period = st.selectbox("Display Period", ["TTM (Current Snapshot)", "10-Year Overview"])

    st.markdown("---")
    st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, on_change=toggle_dark_mode)
    st.caption("Data source: **QuickFS API**")

local_css(st.session_state.dark_mode)

# Fetch Data
json_data = fetch_quickfs_data(target_ticker, API_KEY)

if json_data:
    meta = json_data.get("data", {}).get("metadata", {})
    currency = meta.get("currency", "USD")
    curr_sym = "$" if currency == "USD" else (currency + " ")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"{meta.get('name', target_ticker)}")
        st.markdown(f"#### Ticker: **{target_ticker}** | Currency: **{currency}**")
    st.divider()

    # --- Data Processing ---
    # Extract DataFrame for History View & Raw Data Module
    df_history = extract_historical_df(json_data, years=10)
    
    # Extract Single TTM Values for Cards (from the DataFrame for consistency)
    try:
        # Get column 0 (TTM) values securely
        def get_val(lbl): return df_history.loc[lbl, "TTM"] if (not df_history.empty and lbl in df_history.index) else None
        
        rev = get_val("Revenue")
        gp = get_val("Gross Profit")
        op = get_val("Operating Profit")
        ebitda = get_val("EBITDA")
        ni = get_val("Net Income")
        eps = get_val("EPS (Diluted)")
        nopat = get_val("NOPAT")
        ocf = get_val("Operating Cash Flow")
        fcf = get_val("Free Cash Flow")
    except:
        rev=gp=op=ebitda=ni=eps=nopat=ocf=fcf=None

    # --- VIEW 1: TTM CARDS ---
    if selected_period == "TTM (Current Snapshot)":
        st.subheader("📊 Income Statement")
        c_income = "#3b82f6"
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_card("1. Revenue (Sales) — Top-Line", format_currency(rev, curr_sym), "Top-line sales indicate market demand for the product or service and the size of the operation.", c_income)
        with c2: render_card("2. Gross Profit (Production Efficiency)", format_currency(gp, curr_sym), "Gross profit equals revenue minus the cost of goods sold. It measures a company’s production efficiency—if it’s negative, the company loses money on each product before covering overhead expenses like rent or salaries. COGS (cost of goods sold) includes raw materials, manufacturing costs, and depreciation on production assets such as machinery, factory buildings, production robots, tools and vehicles used in the manufacturing process.", c_income)
        with c3: render_card("3. Operating Profit / EBIT (Profitability)", format_currency(op, curr_sym), "Operating profit equals gross profit minus operating expenses such as marketing, G&A, R&D, and depreciation. G&A (General and Administrative) covers indirect business costs like office rent, utilities, administrative salaries, and insurance, while R&D (Research and Development) covers costs to create or improve products, such as engineers’ salaries, lab work, and testing. It is a key measure of how profitable the core business is, without the effects of taxes and financing decisions.", c_income)
        with c4: render_card("4. EBITDA (Operating Profit)", format_currency(ebitda, curr_sym), "EBITDA stands for Earnings Before Interest, Taxes, Depreciation, and Amortization. It is calculated as operating profit plus depreciation and amortization, and is often used as a proxy for cash flow because non-cash charges like depreciation do not represent actual cash outflows. This makes EBITDA a popular metric for valuing companies, especially in tech and infrastructure sectors, as it focuses on operational cash generation before financing and tax effects.", c_income)
        
        st.markdown(" ") 
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_card("5. NOPAT (After-Tax Operating Profit)", format_currency(nopat, curr_sym), "NOPAT shows the capital allocation efficiency, or how much profit a business makes from its operations after an estimate of taxes, but without including the effects of debt or interest. It is calculated using the formula: NOPAT = EBIT × (1 − Tax Rate). It allows investors to compare companies with different levels of debt (leverage) on an apples-to-apples basis. This “clean” operating profit is commonly used in return metrics like ROIC to assess how efficiently a company uses its capital to generate profits.", c_income)
        with c2: render_card("6. Net Income (Earnings) — Bottom-Line Profit", format_currency(ni, curr_sym), "Net income is the profit left for shareholders after paying all expenses, including suppliers, employees, interest to banks, and taxes. It is the official earnings figure used in metrics like the Price-to-Earnings (P/E) ratio and is influenced by the company’s interest costs, unlike EBIT or NOPAT.", c_income)
        with c3: render_card("7. Earnings Per Share (EPS)", f"{curr_sym}{eps:.2f}" if eps else "N/A", "Earnings per share (EPS) is calculated by dividing net income by the number of common shares outstanding, using only the current, actual shares in existence. It shows how much of today’s profit is allocated to each existing share an investor owns.​", c_income)
        with c4: st.empty() 

        st.markdown("---")

        st.subheader("💸 Cash Flow")
        c_cash = "#10b981"
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_card("8. Operating Cash Flow", format_currency(ocf, curr_sym), "Operating cash flow is the cash from operations that actually comes into or leaves the company from its day-to-day business activities. It adjusts net income for non-cash items and changes in working capital, so sales made on credit (like unpaid invoices in accounts receivable) increase net income but do not increase operating cash flow until the cash is collected.", c_cash)
        with c2: render_card("9. Free Cash Flow (Truly Free Money)", format_currency(fcf, curr_sym), "Free cash flow (FCF) is the cash left over after a company pays for its operating costs and necessary investments in equipment and machinery (CapEx). It represents the truly free money that can be used to pay dividends, buy back shares, or reinvest in growth without hurting the existing business, and because it’s calculated after interest in most cases, it shows how much cash is left for shareholders after servicing debt.", c_cash)
        with c3: st.empty()
        with c4: st.empty()

    # --- VIEW 2: 10-YEAR HISTORY (Chart View) ---
    else:
        st.subheader(f"📅 10-Year Historical Trend")
        if not df_history.empty:
            metric_to_plot = st.selectbox("Select Metric to Visualize", df_history.index.tolist())
            
            # Prepare data for chart: Reverse so time goes Left -> Right
            chart_series = df_history.loc[metric_to_plot]
            # Remove TTM for chart (sometimes confuses scale) or keep it. Let's keep it.
            # Reverse order so Oldest Year is Left, TTM is Right
            chart_data = chart_series.iloc[::-1]
            
            st.bar_chart(chart_data)
        else:
            st.warning("Historical data not available.")

    # --- (3) Expandable Raw Data Module ---
    st.markdown("---")
    with st.expander("📂 View Raw Data (Period Analysis)"):
        st.markdown("### Historical Financials Table")
        if not df_history.empty:
            # Format numbers for display
            df_display = df_history.copy()
            for col in df_display.columns:
                df_display[col] = df_display[col].apply(lambda x: format_currency(x, curr_sym) if pd.notnull(x) else "N/A")
            
            st.dataframe(df_display, use_container_width=True)
            
            st.caption("Columns represent Fiscal Years. TTM = Trailing Twelve Months.")
        else:
            st.info("No raw data generated.")
