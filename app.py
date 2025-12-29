import streamlit as st
import requests

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

# --- Enhanced UI/UX CSS ---
def local_css():
    st.markdown("""
    <style>
        /* Global Reset & Font Scaling */
        html, body, [class*="css"] {
            font-family: 'Inter', 'Roboto', sans-serif; 
            font-size: 1rem;
        }
        
        /* MATERIAL CARD DESIGN 
           Uses Streamlit CSS variables (var(--...)) to support Dark/Light Mode automatically.
        */
        div.metric-card {
            background-color: var(--secondary-background-color); /* Adapts to Dark/Light */
            border: 1px solid rgba(128, 128, 128, 0.1);
            border-radius: 12px; /* Softer corners */
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); /* Subtle shadow */
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        /* Hover Effect: Lift card up */
        div.metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
        }

        /* Label Styling */
        h4.metric-label {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-color);
            opacity: 0.7; /* Muted text for label */
            margin: 0 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* Value Styling */
        div.metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: var(--text-color); /* High contrast */
            margin-bottom: 16px;
        }

        /* Description Styling */
        p.metric-desc {
            font-size: 0.95rem;
            line-height: 1.5;
            color: var(--text-color);
            opacity: 0.6; /* Slightly more muted */
            margin: 0;
            border-top: 1px solid rgba(128, 128, 128, 0.1);
            padding-top: 12px;
        }

        /* Layout Tweaks */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        
        /* Remove default Streamlit top padding */
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- Helper Functions ---
def fetch_quickfs_data(ticker, api_key):
    url = f"https://public-api.quickfs.net/v1/data/all-data/{ticker}?api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {e}")
        return None

def extract_ttm_metric(data, metric_key):
    try:
        financials = data.get("data", {}).get("financials", {})
        keys_to_check = [metric_key] if isinstance(metric_key, str) else metric_key
        
        # 1. Explicit TTM
        for key in keys_to_check:
            if "ttm" in financials and key in financials["ttm"]:
                return financials["ttm"][key]
            
        # 2. Quarterly Sum Fallback
        quarterly = financials.get("quarterly", {})
        for key in keys_to_check:
            if key in quarterly:
                values = quarterly[key]
                if values and len(values) >= 4:
                    valid_values = [v for v in values if v is not None]
                    if len(valid_values) >= 4:
                        return sum(valid_values[-4:])
        return None
    except Exception:
        return None

def format_currency(value, currency_symbol="$"):
    if value is None: return "N/A"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{currency_symbol}{value / 1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{currency_symbol}{value / 1_000_000:.2f}M"
    else:
        return f"{currency_symbol}{value:,.2f}"

def render_card(label, value_str, description, accent_color="#4285F4"):
    """
    Renders a HTML card with a colored accent border.
    accent_color: Hex code for the top border (e.g., Blue for Income, Green for Cash).
    """
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

# --- Main App Logic ---
st.set_page_config(page_title="Financial Dashboard", layout="wide")
local_css()

# Sidebar
with st.sidebar:
    st.header("Search")
    selected_stock_name = st.selectbox("Select Stock", list(STOCKS.keys()))
    selected_ticker = STOCKS[selected_stock_name]
    st.divider()
    st.caption("Data source: **QuickFS API**")
    st.caption("ℹ️ *To enable Dark Mode, go to Settings (top right) → Theme → Dark.*")

# Main Content
json_data = fetch_quickfs_data(selected_ticker, API_KEY)

if json_data:
    meta = json_data.get("data", {}).get("metadata", {})
    currency = meta.get("currency", "USD")
    curr_sym = "$" if currency == "USD" else (currency + " ")

    # Header Section
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title(f"{selected_stock_name}")
        st.markdown(f"#### Ticker: **{selected_ticker}**")
    with col_head2:
        # Just a visual spacer or status
        st.empty()

    st.divider()

    # --- Data Prep ---
    rev = extract_ttm_metric(json_data, "revenue")
    gp = extract_ttm_metric(json_data, "gross_profit")
    op = extract_ttm_metric(json_data, "operating_income")
    ebitda = extract_ttm_metric(json_data, "ebitda")
    ni = extract_ttm_metric(json_data, "net_income")
    eps = extract_ttm_metric(json_data, "eps_diluted")
    
    # NOPAT Calc
    tax = extract_ttm_metric(json_data, "income_tax")
    if op is not None and tax is not None:
        nopat = op - tax
    elif op is not None:
        nopat = op * (1 - 0.21)
    else:
        nopat = None

    ocf = extract_ttm_metric(json_data, ["cf_cfo", "cfo"]) 
    fcf = extract_ttm_metric(json_data, "fcf")

    # --- Section 1: Income Statement (Blue Accent) ---
    st.subheader("📊 Income Statement")
    
    # Colors
    c_income = "#3b82f6" # Blue
    
    # Row 1
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("Revenue", format_currency(rev, curr_sym), "Top-line sales indicating market demand.", c_income)
    with c2: render_card("Gross Profit", format_currency(gp, curr_sym), "Revenue minus cost of goods.", c_income)
    with c3: render_card("Operating Profit", format_currency(op, curr_sym), "Core business profit (EBIT).", c_income)
    with c4: render_card("EBITDA", format_currency(ebitda, curr_sym), "Operational cash flow proxy.", c_income)
    
    st.markdown(" ") # Spacer
    
    # Row 2
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("NOPAT", format_currency(nopat, curr_sym), "Profit if company had no debt.", c_income)
    with c2: render_card("Net Income", format_currency(ni, curr_sym), "The 'Bottom Line' earnings.", c_income)
    with c3: render_card("EPS (Diluted)", f"{curr_sym}{eps:.2f}" if eps else "N/A", "Profit attributed to each share.", c_income)
    with c4: st.empty() 

    st.markdown("---")

    # --- Section 2: Cash Flow (Green Accent) ---
    st.subheader("💸 Cash Flow")
    
    # Colors
    c_cash = "#10b981" # Green
    
    # Row 3
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("Operating Cash Flow", format_currency(ocf, curr_sym), "Cash from actual operations.", c_cash)
    with c2: render_card("Free Cash Flow", format_currency(fcf, curr_sym), "Cash remaining after CapEx.", c_cash)
    with c3: st.empty()
    with c4: st.empty()

else:
    st.error("Failed to load data. Please check your connection or API key.")
