import streamlit as st
import pandas as pd
import numpy as np

from data_engine import download_stock_data, get_data_status

st.set_page_config(
    page_title="Smart Money Scanner Pro",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #0b1220;
    color: #ffffff;
}
[data-testid="stMetric"] {
    background: #172338;
    padding: 18px;
    border-radius: 12px;
}
h1, h2, h3 {
    color: #35d0a0;
}
</style>
""", unsafe_allow_html=True)


def calculate_indicators(df):

    df = df.copy()

    df["EMA20"] = df["Close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["Close"].ewm(
        span=50, adjust=False
    ).mean()

    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    df["AvgVolume20"] = df["Volume"].rolling(20).mean()

    df["VolumePct"] = (
        df["Volume"] / df["AvgVolume20"] - 1
    ) * 100

    df["PreviousHigh20"] = (
        df["High"].rolling(20).max().shift(1)
    )

    df["Breakout"] = (
        df["Close"] > df["PreviousHigh20"]
    )

    return df


def analyze_stock(symbol, market, period, interval,
                  min_volume, min_score):

    data = download_stock_data(
        symbol=symbol,
        market=market,
        period=period,
        interval=interval
    )

    if data is None or len(data) < 55:
        return None

    df = calculate_indicators(data)

    last = df.iloc[-1]

    if pd.isna(last["RSI"]) or pd.isna(last["VolumePct"]):
        return None

    score = 0

    if last["Close"] > last["EMA20"]:
        score += 15

    if last["EMA20"] > last["EMA50"]:
        score += 20

    if 50 <= last["RSI"] <= 70:
        score += 15

    if last["VolumePct"] >= min_volume:
        score += 20

    if last["Breakout"]:
        score += 30

    signal = "No Signal"

    if last["Breakout"] and score >= min_score:
        signal = "Confirmed Breakout"

    elif (
        last["Close"] > last["EMA20"]
        and last["EMA20"] > last["EMA50"]
        and last["VolumePct"] >= min_volume
        and score >= min_score
    ):
        signal = "Early Setup"

    return {
        "Symbol": symbol,
        "Price": round(float(last["Close"]), 2),
        "Volume %": round(float(last["VolumePct"]), 1),
        "RSI": round(float(last["RSI"]), 1),
        "Signal Score": score,
        "Signal": signal,
        "Date": str(df.index[-1].date())
    }


st.title("📈 SMART MONEY SCANNER PRO")
st.caption("Advanced Market Intelligence & Breakout Detection")

st.sidebar.title("CONTROL PANEL")

market = st.sidebar.selectbox(
    "Market",
    ["All Markets", "NASDAQ", "NYSE", "TEL AVIV"]
)

signal_filter = st.sidebar.selectbox(
    "Signal Type",
    ["All Signals", "Early Setup", "Confirmed Breakout"]
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    ["Daily", "Weekly"]
)

st.sidebar.divider()
st.sidebar.subheader("Scanner Settings")

min_volume = st.sidebar.slider(
    "Minimum Volume Increase %",
    0, 200, 10
)

min_score = st.sidebar.slider(
    "Minimum Signal Score",
    0, 100, 60
)

default_symbols = (
    "AAPL, MSFT, NVDA, AMD, TSLA"
    if market != "TEL AVIV"
    else "TEVA, LUMI, POLI"
)

symbols_text = st.sidebar.text_area(
    "Stock Symbols",
    value=default_symbols,
    help="For Israeli stocks, use Yahoo Finance symbols with .TA"
)

symbols = [
    x.strip().upper()
    for x in symbols_text.replace("\n", ",").split(",")
    if x.strip()
]

if market == "NASDAQ":
    symbols = symbols[:]
elif market == "NYSE":
    symbols = symbols[:]
elif market == "TEL AVIV":
    symbols = [
        s if s.endswith(".TA") else s + ".TA"
        for s in symbols
    ]

period = "5y" if timeframe == "Weekly" else "2y"
interval = "1wk" if timeframe == "Weekly" else "1d"

st.divider()

st.subheader("MARKET OVERVIEW")

if st.button("🚀 RUN SMART MONEY SCAN", type="primary"):

    results = []

    progress = st.progress(0)

    for i, symbol in enumerate(symbols):

        result = analyze_stock(
            symbol=symbol,
            market="NASDAQ",
            period=period,
            interval=interval,
            min_volume=min_volume,
            min_score=min_score
        )

        if result:
            results.append(result)

        progress.progress((i + 1) / len(symbols))

    st.session_state["scan_results"] = results

results = st.session_state.get("scan_results", [])

if results:

    df_results = pd.DataFrame(results)

    signals_count = len(
        df_results[df_results["Signal"] != "No Signal"]
    )

    breakouts_count = len(
        df_results[df_results["Signal"] == "Confirmed Breakout"]
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Stocks Scanned", len(df_results))
    c2.metric("Signals", signals_count)
    c3.metric("Breakouts", breakouts_count)
    c4.metric("Data Status", "Connected")

    st.divider()

    if signal_filter != "All Signals":
        df_results = df_results[
            df_results["Signal"] == signal_filter
        ]

    df_results = df_results.sort_values(
        "Signal Score", ascending=False
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Early Setup",
        "📈 Confirmed Breakouts",
        "💰 Smart Money",
        "📊 Backtesting"
    ])

    with tab1:
        st.subheader("Early Setup Scanner")
        st.dataframe(
            df_results[df_results["Signal"] == "Early Setup"],
            use_container_width=True
        )

    with tab2:
        st.subheader("Confirmed Breakout Scanner")
        st.dataframe(
            df_results[
                df_results["Signal"] == "Confirmed Breakout"
            ],
            use_container_width=True
        )

    with tab3:
        st.subheader("Smart Money Analysis")
        st.dataframe(
            df_results[
                ["Symbol", "Volume %", "RSI", "Signal Score"]
            ],
            use_container_width=True
        )

    with tab4:
        st.subheader("Historical Performance")
        st.info("Backtesting engine will be added in the next stage.")

else:

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Markets", "3")
    c2.metric("Signals", "Pending")
    c3.metric("Breakouts", "Pending")
    c4.metric("Data Status", "Waiting")

    st.info("Enter stock symbols and click RUN SMART MONEY SCAN.")

st.divider()

st.caption(
    "SMART MONEY SCANNER PRO | Development Version 0.2"
)
