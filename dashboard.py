import streamlit as st
from supabase import create_client, Client
import plotly.express as px
import pandas as pd
from datetime import datetime
import time

# ========================================
# PAGE CONFIG
# ========================================
st.set_page_config(
    page_title="Symbiotic Dashboard V8",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# SUPABASE CONNECTION
# ========================================
@st.cache_resource
def init_supabase():
    """Initialize Supabase client"""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

# ========================================
# AUTHENTICATION
# ========================================
def login(email, password):
    """Login user"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            st.session_state.authenticated = True
            st.session_state.user_id = response.user.id
            st.session_state.email = email
            return True
        return False
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

def logout():
    """Logout user"""
    supabase.auth.sign_out()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def check_authentication():
    """Check if user is authenticated"""
    return st.session_state.get("authenticated", False)

# ========================================
# DATA FETCHING
# ========================================
@st.cache_data(ttl=30)
def fetch_market_data():
    """Fetch all market data with asset info"""
    try:
        response = supabase.table('market_data')\
            .select('*, assets(id, name, symbol, type, currency)')\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching market data: {str(e)}")
        return []

@st.cache_data(ttl=30)
def fetch_system_health():
    """Fetch system health"""
    try:
        response = supabase.table('system_health').select('*').execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching system health: {str(e)}")
        return []

# ========================================
# MAIN DASHBOARD
# ========================================
def main():
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        st.write(f"👤 **{st.session_state.email}**")
        
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            logout()
    
    # Title
    st.title("📈 Symbiotic Dashboard V8")
    st.caption("⚡ Powered by Supabase - Real-time market intelligence")
    
    # Auto-refresh every 60 seconds
    st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")
    time.sleep(1)
    
    # Fetch data
    market_data = fetch_market_data()
    system_health = fetch_system_health()
    
    if not market_data:
        st.warning("⚠️ No market data available. Run the update-prices function first!")
        st.info("Go to: https://supabase.com/dashboard/project/pyfsoweyuozsnhnkzmet/functions/update-prices")
        return
    
    # Separate crypto and stocks
    crypto_data = [d for d in market_data if d['assets']['type'] == 'crypto']
    stock_data = [d for d in market_data if d['assets']['type'] == 'stock']
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_assets = len(market_data)
    crypto_count = len(crypto_data)
    stock_count = len(stock_data)
    
    # Calculate average change
    avg_change = sum([d.get('price_change_pct', 0) or 0 for d in market_data]) / max(total_assets, 1)
    
    col1.metric("Total Assets", total_assets)
    col2.metric("Cryptocurrencies", crypto_count)
    col3.metric("Stocks", stock_count)
    col4.metric("Avg Change", f"{avg_change:+.2f}%")
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Market Overview", "💰 Crypto", "📈 Stocks"])
    
    with tab1:
        st.header("Market Overview")
        
        # Create price chart data
        if market_data:
            df = pd.DataFrame([{
                'Asset': d['assets']['name'],
                'Price': d['price'],
                'Change %': d.get('price_change_pct', 0) or 0,
                'Type': d['assets']['type'].capitalize()
            } for d in market_data])
            
            # Price comparison chart
            fig = px.bar(df, x='Asset', y='Change %', color='Type',
                        title='Price Changes (%)',
                        color_discrete_map={'Crypto': '#f7931a', 'Stock': '#4285f4'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Data table
            st.markdown("### Current Prices")
            st.dataframe(df.style.format({
                'Price': '£{:.2f}',
                'Change %': '{:+.2f}%'
            }), use_container_width=True)
    
    with tab2:
        st.header("Cryptocurrency Prices")
        
        if crypto_data:
            for crypto in crypto_data:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.subheader(crypto['assets']['name'])
                        st.caption(f"Symbol: {crypto['assets']['symbol']}")
                    
                    with col2:
                        currency = "£" if crypto['assets']['currency'] == 'GBP' else "$"
                        st.metric("Price", f"{currency}{crypto['price']:,.2f}")
                    
                    with col3:
                        change = crypto.get('price_change_pct', 0) or 0
                        st.metric("24h Change", f"{change:+.2f}%",
                                delta=f"{change:+.2f}%",
                                delta_color="normal" if change >= 0 else "inverse")
        else:
            st.info("No cryptocurrency data available")
    
    with tab3:
        st.header("Stock Prices")
        
        if stock_data:
            for stock in stock_data:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.subheader(stock['assets']['name'])
                        st.caption(f"Ticker: {stock['assets']['symbol']}")
                    
                    with col2:
                        currency = "$" if stock['assets']['currency'] == 'USD' else "£"
                        st.metric("Price", f"{currency}{stock['price']:,.2f}")
                    
                    with col3:
                        change = stock.get('price_change_pct', 0) or 0
                        st.metric("Change", f"{change:+.2f}%",
                                delta=f"{change:+.2f}%",
                                delta_color="normal" if change >= 0 else "inverse")
        else:
            st.info("No stock data available")
    
    # System Health
    st.markdown("---")
    st.subheader("🏥 System Health")
    
    health_cols = st.columns(len(system_health))
    for idx, component in enumerate(system_health):
        with health_cols[idx]:
            status = component['status']
            if status == 'healthy':
                st.success(f"✅ {component['component']}")
            elif status == 'degraded':
                st.warning(f"⚠️ {component['component']}")
            else:
                st.error(f"❌ {component['component']}")
            
            st.caption(component['message'])

# ========================================
# LOGIN SCREEN
# ========================================
def login_screen():
    st.markdown("<h1 style='text-align: center;'>🔐 Symbiotic Dashboard V8</h1>", 
                unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Enhanced Edition - Powered by Supabase</p>", 
                unsafe_allow_html=True)
    
    _, center, _ = st.columns([1, 2, 1])
    
    with center:
        st.markdown("---")
        email = st.text_input("Email", placeholder="your@email.com")
        password = st.text_input("Password", type="password")
        st.markdown("---")
        
        if st.button("🔓 Login", use_container_width=True, type="primary"):
            if login(email, password):
                st.success("✅ Login successful!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ Invalid credentials")

# ========================================
# ROUTING
# ========================================
if __name__ == "__main__":
    if check_authentication():
        main()
    else:
        login_screen()