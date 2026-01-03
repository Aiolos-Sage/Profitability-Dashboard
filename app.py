import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

# --- Configuration ---
try:
    API_KEY = st.secrets["QUICKFS_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("🚨 API Key missing! Please add `QUICKFS_API_KEY` to your `.streamlit/secrets.toml` file.")
    st.stop()

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
        btn_bg = "#d93025" 
        btn_text = "#ffffff"
    else:
        bg_color = "#ffffff"
        text_color = "#000000"
        card_bg = "#ffffff"
        border_color = "rgba(128, 128, 128, 0.1)"
        shadow_color = "rgba(0, 0, 0, 0.05)"
        label_color = "#5f6368"
        desc_color = "#70757a"
        btn_bg = "#d93025"
        btn_text = "#ffffff"

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
        
        /* Custom Button Style */
        div.stButton > button {{
            background-color: {btn_bg};
            color: {btn_text};
            border: none;
            border-radius: 4px;
            padding: 0.5rem 1rem;
            font-weight: 500;
            width: 100%;
        }}
        div.stButton > button:hover {{
            background-color: #b0281f; 
            color: {btn_text};
        }}
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

def extract_historical_df(data, start_year, end_year):
    """
    Robust extraction of historical data using Pandas for alignment.
    Prevents 'max() empty sequence' errors and handles mismatched list lengths.
    """
    try:
        # 1. Access Nested Data Safely
        fin = data.get("data", {}).get("financials", {})
        annual = fin.get("annual", {})
        ttm_data = fin.get("ttm", {})
        meta = data.get("data", {}).get("metadata", {})
        
        # 2. Extract and Parse Years
        raw_dates = meta.get("period_end_date", [])
        if not raw_dates:
            return pd.DataFrame() # Graceful exit if no dates

        # Convert dates "2012-12-31" to integers [2012, 2013...]
        years = []
        for d in raw_dates:
            try:
                years.append(int(str(d).split("-")[0]))
            except:
                pass # Skip bad formats
        
        if not years:
            return pd.DataFrame() # Graceful exit if parsing failed

        # 3. Define Metrics Map
        metrics_map = {
            "Revenue": ["revenue"],
            "Gross Profit": ["gross_profit"],
            "Operating Profit": ["operating_income"],
            "EBITDA": ["ebitda"],
            "NOPAT": ["nopat_derived"],
            "Net Income": ["net_income"],
            "EPS (Diluted)": ["eps_diluted"],
            "Operating Cash Flow": ["cf_cfo", "cfo"],
            "Free Cash Flow": ["fcf"]
        }

        # 4. Construct Full DataFrame (Annual Data)
        # We build a dictionary {Metric: [Values...]} then DataFrame it
        df_data = {}
        
        for label, keys in metrics_map.items():
            # Find the first key that exists in annual data
            valid_key = next((k for k in keys if k in annual), None)
            values = []

            if valid_key:
                values = annual[valid_key]
                # Fallback for NOPAT manual calc if key exists but is empty, or pure fallback
                if label == "NOPAT" and (not values or valid_key == "nopat_derived"):
                    # Check if empty, try calculating
                    if not values:
                        op_hist = annual.get("operating_income", [])
                        tax_hist = annual.get("income_tax", [])
                        if op_hist and tax_hist:
                             # Zip allows partial calc if lengths differ
                             values = [(o or 0) - (t or 0) for o, t in zip(op_hist, tax_hist)]
            
            # Align list length with years length
            # If data is shorter/longer, pandas handles index alignment better, 
            # but here we just pad to be safe for list construction
            if values:
                if len(values) < len(years):
                    values = values + [None] * (len(years) - len(values))
                elif len(values) > len(years):
                    values = values[:len(years)]
            else:
                values = [None] * len(years)

            df_data[label] = values

        # Create DataFrame indexed by Year
        df = pd.DataFrame(df_data, index=years)
        
        # 5. Filter by Start/End Year
        # Sort index to ensure range works (oldest -> newest)
        df.sort_index(inplace=True)
        
        target_start = int(start_year)
        
        if end_year == "TTM":
            target_end = df.index.max() if not df.empty else 2100 # Default huge if empty
        else:
            target_end = int(end_year)

        # Boolean Mask Filter
        df_filtered = df[(df.index >= target_start) & (df.index <= target_end)].transpose()
        
        # 6. Append TTM Column if requested
        if end_year == "TTM":
            ttm_col = []
            for label in df_filtered.index:
                keys = metrics_map[label]
                
                # Fetch TTM
                val = None
                # Try explicit TTM key
                for k in keys:
                    if k in ttm_data:
                        val = ttm_data[k]
                        break
                
                # NOPAT TTM Calc Fallback
                if label == "NOPAT" and val is None:
                    op = ttm_data.get("operating_income")
                    tax = ttm_data.get("income_tax")
                    if op is not None:
                        val = (op - tax) if tax is not None else (op * 0.79) # 21% tax rate assumption

                ttm_col.append(val)
            
            # Add as new column
            df_filtered["TTM"] = ttm_col

        return df_filtered

    except Exception as e:
        # In production, you might want to log 'e'
        return pd.DataFrame()

def format_currency(value, currency_symbol="$"):
    if value is None: return "N/A"
    try:
        abs_val = abs(value)
        if abs_val >= 1_000_000_000: return f"{currency_symbol}{value / 1_000_000_000:.2f}B"
        elif abs_val >= 1_000_000: return f"{currency_symbol}{value / 1_000_000:.2f}M"
        else: return f"{currency_symbol}{value:,.2f}"
    except:
        return "N/A"

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

# (1) Clean Sidebar - Dark Mode Only
with st.sidebar:
    st.header("Settings")
    st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, on_change=toggle_dark_mode)
    st.markdown("---")
    st.caption("Data source: **QuickFS API**")

local_css(st.session_state.dark_mode)

# (3) Search & Filter Layout
col_search, col_btn = st.columns([4, 1])
with col_search:
    search_input = st.text_input("Enter Ticker", placeholder="e.g. APG:US", label_visibility="collapsed")
with col_btn:
    load_btn = st.button("Load Financials")

st.markdown("---")

col_start, col_end = st.columns(2)
current_year = datetime.now().year
years_options = list(range(2000, current_year + 1))
years_options_str = [str(y) for y in years_options]

with col_start:
    # Default to 5 years ago if possible
    default_start_idx = len(years_options_str) - 6 if len(years_options_str) > 6 else 0
    start_year_sel = st.selectbox("Start Year", years_options_str, index=default_start_idx)

with col_end:
    end_options = years_options_str + ["TTM"]
    end_year_sel = st.selectbox("End Year", end_options, index=len(end_options)-1)

st.markdown("---")

# Logic to load data
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = None
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = ""

if load_btn and search_input:
    ticker = search_input.strip()
    with st.spinner(f"Loading data for {ticker}..."):
        data = fetch_quickfs_data(ticker, API_KEY)
        if data:
            st.session_state.data_cache = data
            st.session_state.current_ticker = ticker
        else:
            st.session_state.data_cache = None

# Display Data if available
if st.session_state.data_cache:
    json_data = st.session_state.data_cache
    ticker = st.session_state.current_ticker
    
    meta = json_data.get("data", {}).get("metadata", {})
    currency = meta.get("currency", "USD")
    curr_sym = "$" if currency == "USD" else (currency + " ")

    st.markdown(f"## {meta.get('name', ticker)} <span style='font-size:1.2rem; color: gray'>({ticker})</span>", unsafe_allow_html=True)
    st.caption(f"Reporting Currency: {currency}")

    # Validate Dates
    valid_range = True
    if end_year_sel != "TTM" and int(end_year_sel) < int(start_year_sel):
        st.warning("⚠️ End Year cannot be before Start Year.")
        valid_range = False

    if valid_range:
        df_display = extract_historical_df(json_data, start_year_sel, end_year_sel)
        
        if not df_display.empty:
            # --- VIEW 1: Cards (Displaying Latest Available Data in Selection) ---
            latest_col = df_display.columns[-1]
            st.subheader(f"📊 Snapshot ({latest_col})")
            
            def get_val(lbl): return df_display.loc[lbl, latest_col] if lbl in df_display.index else None
            
            rev = get_val("Revenue")
            gp = get_val("Gross Profit")
            op = get_val("Operating Profit")
            ebitda = get_val("EBITDA")
            ni = get_val("Net Income")
            eps = get_val("EPS (Diluted)")
            nopat = get_val("NOPAT")
            ocf = get_val("Operating Cash Flow")
            fcf = get_val("Free Cash Flow")

            # Descriptions
            desc_revenue = "Top-line sales indicate market demand for the product or service and the size of the operation."
            desc_gp = "Gross profit equals revenue minus the cost of goods sold. It measures a company’s production efficiency."
            desc_op = "Operating profit equals gross profit minus operating expenses (Marketing, G&A, R&D). Core profitability."
            desc_ebitda = "Earnings Before Interest, Taxes, Depreciation, and Amortization. Proxy for cash flow."
            desc_nopat = "NOPAT shows potential cash earnings if the company had no debt (unlevered)."
            desc_ni = "Net income is the profit left for shareholders after all expenses and taxes."
            desc_eps = "Earnings per share (EPS) shows how much profit is allocated to each share."
            desc_ocf = "Cash actually generated from day-to-day business operations."
            desc_fcf = "Cash left over after operating costs and CapEx. Truly free money for shareholders."

            c_income = "#3b82f6"
            c1, c2, c3, c4 = st.columns(4)
            with c1: render_card("Revenue", format_currency(rev, curr_sym), desc_revenue, c_income)
            with c2: render_card("Gross Profit", format_currency(gp, curr_sym), desc_gp, c_income)
            with c3: render_card("Operating Profit", format_currency(op, curr_sym), desc_op, c_income)
            with c4: render_card("EBITDA", format_currency(ebitda, curr_sym), desc_ebitda, c_income)
            
            st.markdown(" ") 
            c1, c2, c3, c4 = st.columns(4)
            with c1: render_card("NOPAT", format_currency(nopat, curr_sym), desc_nopat, c_income)
            with c2: render_card("Net Income", format_currency(ni, curr_sym), desc_ni, c_income)
            with c3: render_card("EPS (Diluted)", f"{curr_sym}{eps:.2f}" if eps else "N/A", desc_eps, c_income)
            with c4: st.empty() 

            st.markdown("---")

            st.subheader(f"💸 Cash Flow ({latest_col})")
            c_cash = "#10b981"
            c1, c2, c3, c4 = st.columns(4)
            with c1: render_card("Operating Cash Flow", format_currency(ocf, curr_sym), desc_ocf, c_cash)
            with c2: render_card("Free Cash Flow", format_currency(fcf, curr_sym), desc_fcf, c_cash)
            with c3: st.empty()
            with c4: st.empty()

            # --- VIEW 2: Raw Data ---
            st.markdown("---")
            with st.expander("📂 View Raw Data (Selected Period)", expanded=True):
                st.markdown("### Historical Financials Table")
                df_fmt = df_display.copy()
                for col in df_fmt.columns:
                    df_fmt[col] = df_fmt[col].apply(lambda x: format_currency(x, curr_sym) if pd.notnull(x) else "N/A")
                st.dataframe(df_fmt, use_container_width=True)
                
                st.markdown("### Trend Visualization")
                metric_to_plot = st.selectbox("Select Metric", df_display.index.tolist())
                # Ensure data is numeric for plotting
                st.bar_chart(df_display.loc[metric_to_plot])
        else:
            # Fallback for empty DF: Show the "Start Year" might be too recent
            st.warning(f"No data found between {start_year_sel} and {end_year_sel}. Try selecting an earlier Start Year.")

elif load_btn and not search_input:
    st.warning("Please enter a ticker symbol.")
