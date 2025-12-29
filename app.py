# --- Custom CSS for Material Design ---
def local_css():
    st.markdown("""
    <style>
        /* Enforce minimum 1rem across the entire Streamlit App */
        html, body, .stApp {
            font-size: 1rem; /* Base size */
        }

        /* Metric Card Style */
        div.metric-card {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15);
            margin-bottom: 20px;
            height: 100%;
            transition: box-shadow 0.2s ease-in-out;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        
        div.metric-card:hover {
            box-shadow: 0 4px 8px 3px rgba(60,64,67,0.15);
        }

        /* Typography Updates for 1rem Minimum */
        
        /* Label: Slightly larger than min to distinguish from body text */
        h4.metric-label {
            font-family: 'Roboto', sans-serif;
            font-size: 1.1rem; /* Increased from 14px */
            font-weight: 500;
            color: #5f6368;
            margin: 0 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Value: Large and bold for emphasis */
        div.metric-value {
            font-family: 'Google Sans', 'Roboto', sans-serif;
            font-size: 2.5rem; /* Increased from 28px */
            font-weight: 400;
            color: #202124;
            margin-bottom: 12px;
        }
        
        /* Description: The minimum allowed size */
        p.metric-desc {
            font-family: 'Roboto', sans-serif;
            font-size: 1rem; /* Increased from 12px */
            line-height: 1.6;
            color: #70757a;
            margin: 0;
            border-top: 1px solid #f1f3f4;
            padding-top: 10px;
        }
        
        /* Force Streamlit's default small text (like captions/widgets) to respect the minimum */
        .stMarkdown p, .stCaption, .stText, small, label {
            font-size: 1rem !important;
        }
        
        /* Adjust layout spacing */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)
