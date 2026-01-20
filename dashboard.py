import streamlit as st
from supabase import create_client, Client
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
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
            .order('assets(type)', desc=False)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching market data: {str(e)}")
        return []

@st.cache_data(ttl=30)
def fetch_holdings():
    """Fetch user's portfolio holdings"""
    try:
        user_id = st.session_state.get('user_id')
        if not user_id:
            return []
        
        # Fetch holdings
        response = supabase.table('holdings')\
            .select('*')\
            .eq('user_id', user_id)\
            .execute()
        
        holdings = response.data
        
        # Manually fetch asset info for each holding by ticker
        if holdings:
            for holding in holdings:
                ticker = holding.get('ticker')
                if ticker:
                    # Try to find matching asset by symbol
                    asset_response = supabase.table('assets')\
                        .select('*')\
                        .eq('symbol', ticker)\
                        .limit(1)\
                        .execute()
                    
                    if asset_response.data:
                        holding['assets'] = asset_response.data[0]
                    else:
                        # Create a fake asset object if not found
                        holding['assets'] = {
                            'id': None,
                            'name': holding.get('company_name', ticker),
                            'symbol': ticker,
                            'type': 'stock',  # Assume stock from Trading212
                            'currency': 'GBP'
                        }
                
                # Map holdings columns to expected names
                holding['average_price'] = holding.get('avg_price', 0)
                holding['current_price'] = holding.get('avg_price', 0)  # We don't have current_price in holdings
                holding['cost_basis'] = (holding.get('avg_price', 0) or 0) * (holding.get('quantity', 0) or 0)
        
        return holdings
    except Exception as e:
        st.error(f"Error fetching holdings: {str(e)}")
        return []

@st.cache_data(ttl=30)
def fetch_signals():
    """Fetch trading signals"""
    try:
        response = supabase.table('signals')\
            .select('*, assets(id, name, symbol, type, currency)')\
            .order('score', desc=True)\
            .limit(20)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching signals: {str(e)}")
        return []

@st.cache_data(ttl=300)
def fetch_prediction_markets():
    """Fetch Polymarket prediction data"""
    try:
        response = supabase.table('predictions')\
            .select('*')\
            .order('volume', desc=True)\
            .limit(10)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching prediction markets: {str(e)}")
        return []

@st.cache_data(ttl=30)
def fetch_system_health():
    """Fetch system health"""
    try:
        response = supabase.table('system_health')\
            .select('*')\
            .order('updated_at', desc=True)\
            .limit(5)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching system health: {str(e)}")
        return []

# ========================================
# VISUALIZATION HELPERS
# ========================================
def create_portfolio_pie_chart(holdings):
    """Create pie chart of portfolio allocation"""
    if not holdings:
        return None
    
    df = pd.DataFrame([{
        'Asset': h['assets']['name'],
        'Value': h.get('current_value', 0) or 0
    } for h in holdings if h.get('current_value', 0) > 0])
    
    if df.empty:
        return None
    
    fig = px.pie(df, values='Value', names='Asset',
                 title='Portfolio Allocation',
                 color_discrete_sequence=px.colors.qualitative.Set3)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

def create_risk_gauge(concentration_score):
    """Create concentration risk gauge"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=concentration_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Concentration Risk"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 33], 'color': "lightgreen"},
                {'range': [33, 66], 'color': "yellow"},
                {'range': [66, 100], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 75
            }
        }
    ))
    fig.update_layout(height=250)
    return fig

def create_correlation_heatmap(market_data):
    """Create correlation matrix heatmap"""
    if len(market_data) < 2:
        return None
    
    # Create price change matrix
    assets = [d['assets']['name'] for d in market_data]
    changes = [d.get('price_change_pct', 0) or 0 for d in market_data]
    
    # For demo, create random correlation matrix
    # In production, use historical price data
    n = len(assets)
    corr_matrix = np.eye(n) + np.random.randn(n, n) * 0.3
    corr_matrix = (corr_matrix + corr_matrix.T) / 2
    np.fill_diagonal(corr_matrix, 1)
    corr_matrix = np.clip(corr_matrix, -1, 1)
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=assets,
        y=assets,
        colorscale='RdBu',
        zmid=0,
        text=corr_matrix,
        texttemplate='%{text:.2f}',
        textfont={"size": 10}
    ))
    
    fig.update_layout(
        title='Asset Correlation Matrix',
        height=500,
        xaxis={'tickangle': -45}
    )
    return fig

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
        
        st.markdown("---")
        st.subheader("🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable auto-refresh (60s)", value=True)
        
        if auto_refresh:
            st.info("Dashboard refreshes every 60 seconds")
    
    # Title
    st.title("📈 Symbiotic Dashboard V8")
    st.caption("⚡ Powered by Supabase - Real-time market intelligence")
    
    # Auto-refresh
    st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M:%S')}*")
    
    # Fetch all data
    market_data = fetch_market_data()
    holdings = fetch_holdings()
    signals = fetch_signals()
    prediction_markets = fetch_prediction_markets()
    system_health = fetch_system_health()
    
    if not market_data:
        st.warning("⚠️ No market data available. Run the update-prices Edge Function first!")
        st.info("Go to: Supabase Dashboard → Edge Functions → update-prices → Invoke")
        return
    
    # Separate crypto and stocks
    crypto_data = [d for d in market_data if d['assets']['type'] == 'crypto']
    stock_data = [d for d in market_data if d['assets']['type'] == 'stock']
    
    # Calculate portfolio value
    total_portfolio_value = sum([h.get('current_value', 0) or 0 for h in holdings])
    total_holdings_count = len([h for h in holdings if h.get('quantity', 0) > 0])
    
    # Top metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_assets = len(market_data)
    crypto_count = len(crypto_data)
    stock_count = len(stock_data)
    avg_change = sum([d.get('price_change_pct', 0) or 0 for d in market_data]) / max(total_assets, 1)
    
    col1.metric("Total Assets", total_assets)
    col2.metric("Cryptocurrencies", crypto_count)
    col3.metric("Stocks", stock_count)
    col4.metric("Avg Change", f"{avg_change:+.2f}%")
    col5.metric("Portfolio Value", f"£{total_portfolio_value:,.2f}")
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Market Overview",
        "💼 Portfolio",
        "🎯 Trading Signals",
        "⚠️ Risk Assessment",
        "🔮 Prediction Markets",
        "📰 System Health"
    ])
    
    # ========================================
    # TAB 1: MARKET OVERVIEW
    # ========================================
    with tab1:
        st.header("Market Overview")
        
        # Create price chart data
        if market_data:
            df = pd.DataFrame([{
                'Asset': d['assets']['name'],
                'Symbol': d['assets']['symbol'],
                'Price': d['price'],
                'Change %': d.get('price_change_pct', 0) or 0,
                'Type': d['assets']['type'].capitalize(),
                'RSI': d.get('rsi', 0) or 0,
                'Volume': d.get('volume_24h', 0) or 0
            } for d in market_data])
            
            # Price comparison chart
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(df, x='Asset', y='Change %', color='Type',
                            title='24h Price Changes (%)',
                            color_discrete_map={'Crypto': '#f7931a', 'Stock': '#4285f4'})
                fig.update_layout(height=400, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # RSI distribution
                fig_rsi = px.histogram(df[df['RSI'] > 0], x='RSI', nbins=20,
                                      title='RSI Distribution',
                                      color_discrete_sequence=['#00D9FF'])
                fig_rsi.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig_rsi.add_vline(x=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig_rsi.update_layout(height=400)
                st.plotly_chart(fig_rsi, use_container_width=True)
            
            # Data table
            st.markdown("### 📋 Current Prices")
            display_df = df[['Asset', 'Symbol', 'Price', 'Change %', 'RSI', 'Type']]
            st.dataframe(
                display_df.style.format({
                    'Price': '£{:.2f}',
                    'Change %': '{:+.2f}%',
                    'RSI': '{:.1f}'
                }).applymap(
                    lambda x: 'background-color: #90EE90' if isinstance(x, (int, float)) and x > 0 else 
                             ('background-color: #FFB6C1' if isinstance(x, (int, float)) and x < 0 else ''),
                    subset=['Change %']
                ),
                use_container_width=True,
                height=400
            )
    
    # ========================================
    # TAB 2: PORTFOLIO
    # ========================================
    with tab2:
        st.header("💼 My Portfolio")
        
        if total_holdings_count == 0:
            st.info("📭 No holdings found. Connect your Trading212 account via Edge Functions.")
        else:
            # Portfolio metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_cost = sum([h.get('cost_basis', 0) or 0 for h in holdings])
            total_gain = total_portfolio_value - total_cost
            total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0
            
            col1.metric("Total Value", f"£{total_portfolio_value:,.2f}")
            col2.metric("Total Cost", f"£{total_cost:,.2f}")
            col3.metric("Total Gain/Loss", f"£{total_gain:+,.2f}", 
                       delta=f"{total_gain_pct:+.2f}%")
            col4.metric("Holdings", total_holdings_count)
            
            # Portfolio pie chart
            col1, col2 = st.columns(2)
            
            with col1:
                pie_chart = create_portfolio_pie_chart(holdings)
                if pie_chart:
                    st.plotly_chart(pie_chart, use_container_width=True)
                else:
                    st.info("No holdings with value > £0")
            
            with col2:
                # Holdings breakdown
                st.markdown("### 📊 Holdings Breakdown")
                holdings_df = pd.DataFrame([{
                    'Asset': h['assets']['name'],
                    'Quantity': h.get('quantity', 0) or 0,
                    'Avg Price': h.get('average_price', 0) or 0,
                    'Current Price': h.get('current_price', 0) or 0,
                    'Value': h.get('current_value', 0) or 0,
                    'Gain/Loss %': ((h.get('current_price', 0) or 0) / max(h.get('average_price', 1), 0.01) - 1) * 100
                } for h in holdings if h.get('quantity', 0) > 0])
                
                if not holdings_df.empty:
                    st.dataframe(
                        holdings_df.style.format({
                            'Quantity': '{:.4f}',
                            'Avg Price': '£{:.2f}',
                            'Current Price': '£{:.2f}',
                            'Value': '£{:.2f}',
                            'Gain/Loss %': '{:+.2f}%'
                        }).applymap(
                            lambda x: 'background-color: #90EE90' if isinstance(x, (int, float)) and x > 0 else 
                                     ('background-color: #FFB6C1' if isinstance(x, (int, float)) and x < 0 else ''),
                            subset=['Gain/Loss %']
                        ),
                        use_container_width=True,
                        height=400
                    )
    
    # ========================================
    # TAB 3: TRADING SIGNALS
    # ========================================
    with tab3:
        st.header("🎯 Trading Signals")
        
        if not signals:
            st.info("📭 No signals available. Run the signal generation Edge Function.")
        else:
            # Filter signals
            col1, col2, col3 = st.columns(3)
            
            with col1:
                signal_filter = st.selectbox("Filter by Signal", 
                                            ["All", "BUY", "SELL", "HOLD"])
            with col2:
                type_filter = st.selectbox("Filter by Type",
                                          ["All", "Crypto", "Stock"])
            with col3:
                min_score = st.slider("Minimum Confidence Score", 0, 100, 0)
            
            # Apply filters
            filtered_signals = signals
            if signal_filter != "All":
                filtered_signals = [s for s in filtered_signals if s.get('signal') == signal_filter]
            if type_filter != "All":
                filtered_signals = [s for s in filtered_signals 
                                   if s['assets']['type'] == type_filter.lower()]
            filtered_signals = [s for s in filtered_signals if (s.get('score', 0) or 0) >= min_score]
            
            # Display signals
            st.markdown(f"### 📊 {len(filtered_signals)} Signals")
            
            for signal in filtered_signals:
                signal_type = signal.get('signal', 'HOLD')
                score = signal.get('score', 0) or 0
                
                # Color based on signal
                if signal_type == 'BUY':
                    color = '🟢'
                    border_color = 'green'
                elif signal_type == 'SELL':
                    color = '🔴'
                    border_color = 'red'
                else:
                    color = '🟡'
                    border_color = 'gray'
                
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    
                    with col1:
                        st.markdown(f"### {color} {signal['assets']['name']}")
                        st.caption(f"Symbol: {signal['assets']['symbol']} | Type: {signal['assets']['type'].upper()}")
                    
                    with col2:
                        st.metric("Signal", signal_type)
                    
                    with col3:
                        st.metric("Confidence", f"{score}/100")
                    
                    with col4:
                        rsi = signal.get('rsi', 0) or 0
                        if rsi > 0:
                            st.metric("RSI", f"{rsi:.1f}")
                    
                    # Reasoning
                    if signal.get('reasoning'):
                        with st.expander("📝 Signal Reasoning"):
                            st.write(signal['reasoning'])
    
    # ========================================
    # TAB 4: RISK ASSESSMENT
    # ========================================
    with tab4:
        st.header("⚠️ Risk Assessment")
        
        if total_holdings_count == 0:
            st.info("📭 No holdings to assess risk. Add holdings first.")
        else:
            # Calculate concentration risk
            holdings_values = [h.get('current_value', 0) or 0 for h in holdings if h.get('current_value', 0) > 0]
            if holdings_values:
                max_holding_pct = (max(holdings_values) / sum(holdings_values)) * 100
                concentration_score = min(max_holding_pct * 1.5, 100)
            else:
                concentration_score = 0
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Concentration risk gauge
                gauge = create_risk_gauge(concentration_score)
                if gauge:
                    st.plotly_chart(gauge, use_container_width=True)
                
                # Risk interpretation
                if concentration_score < 33:
                    st.success("✅ **Low Risk** - Well diversified portfolio")
                elif concentration_score < 66:
                    st.warning("⚠️ **Medium Risk** - Consider diversifying further")
                else:
                    st.error("🚨 **High Risk** - Portfolio heavily concentrated!")
            
            with col2:
                st.markdown("### 📊 Risk Metrics")
                
                # Volatility (simplified - using price changes as proxy)
                price_changes = [d.get('price_change_pct', 0) or 0 for d in market_data]
                volatility = np.std(price_changes) if price_changes else 0
                
                st.metric("Portfolio Volatility", f"{volatility:.2f}%")
                st.metric("Largest Position", f"{max_holding_pct:.1f}%" if holdings_values else "0%")
                st.metric("Number of Positions", total_holdings_count)
                
                # Risk recommendations
                st.markdown("### 💡 Recommendations")
                if concentration_score > 50:
                    st.markdown("- Consider reducing largest position")
                    st.markdown("- Add more diversified assets")
                if volatility > 5:
                    st.markdown("- High volatility detected")
                    st.markdown("- Consider defensive positions")
            
            # Correlation matrix
            if len(market_data) >= 2:
                st.markdown("---")
                corr_heatmap = create_correlation_heatmap(market_data)
                if corr_heatmap:
                    st.plotly_chart(corr_heatmap, use_container_width=True)
    
    # ========================================
    # TAB 5: PREDICTION MARKETS
    # ========================================
    with tab5:
        st.header("🔮 Prediction Markets (Polymarket)")
        
        if not prediction_markets:
            st.info("📭 No prediction market data available. Run the Polymarket Edge Function.")
        else:
            st.markdown("### 🎲 Top Markets by Volume")
            
            for market in prediction_markets:
                probability = (market.get('probability', 0) or 0) * 100
                volume = market.get('volume', 0) or 0
                
                # Determine confidence level
                if probability > 80 or probability < 20:
                    confidence = "🔥 High"
                    color = "green" if probability > 50 else "red"
                elif probability > 65 or probability < 35:
                    confidence = "⚡ Medium"
                    color = "orange"
                else:
                    confidence = "📊 Uncertain"
                    color = "gray"
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{market.get('title', 'Unknown')}**")
                        st.caption(market.get('category', 'General'))
                    
                    with col2:
                        st.metric("Probability", f"{probability:.1f}%")
                    
                    with col3:
                        st.metric("Confidence", confidence)
                    
                    # Additional details
                    if market.get('end_date'):
                        st.caption(f"🗓️ Ends: {market['end_date']}")
                    if volume > 0:
                        st.caption(f"💰 Volume: ${volume:,.0f}")
    
    # ========================================
    # TAB 6: SYSTEM HEALTH
    # ========================================
    with tab6:
        st.header("📰 System Health")
        
        if not system_health:
            st.info("📭 No system health data available.")
        else:
            # Overall health status
            healthy_components = len([h for h in system_health if h.get('status') == 'healthy'])
            total_components = len(system_health)
            health_pct = (healthy_components / total_components * 100) if total_components > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("System Health", f"{health_pct:.0f}%")
            col2.metric("Healthy Components", f"{healthy_components}/{total_components}")
            col3.metric("Last Check", system_health[0].get('updated_at', 'Unknown')[:16] if system_health else 'Unknown')
            
            st.markdown("---")
            
            # Component details
            for component in system_health:
                status = component.get('status', 'unknown')
                component_name = component.get('component', 'Unknown')
                message = component.get('message', 'No details available')
                
                if status == 'healthy':
                    st.success(f"✅ **{component_name}** - {message}")
                elif status == 'degraded':
                    st.warning(f"⚠️ **{component_name}** - {message}")
                else:
                    st.error(f"❌ **{component_name}** - {message}")
            
            # Refresh button
            if st.button("🔄 Refresh System Health", type="primary"):
                st.cache_data.clear()
                st.rerun()

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
