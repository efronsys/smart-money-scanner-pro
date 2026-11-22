
import streamlit as st
import pandas as pd
import numpy as np

from datetime import datetime

from data_engine import (
    download_stock_data,
    get_data_status
)


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="SMART MONEY SCANNER PRO",
    page_icon="📈",
    layout="wide"
)


# =========================================================
# DESIGN
# =========================================================

st.markdown("""
<style>
    .stApp {
        background-color: #0b1120;
        color: #e5e7eb;
    }

    h1, h2, h3 {
        color: #38bdf8;
    }

    div[data-testid="stMetric"] {
        background-color: #172033;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #263449;
    }

    div[data-testid="stMetricValue"] {
        color: #38bdf8;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# TITLE
# =========================================================

st.title("📈 SMART MONEY SCANNER PRO")

st.caption(
    "Technical Market Scanner | Nasdaq | NYSE | Tel Aviv"
)

st.divider()


# =========================================================
# INDICATORS
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    # Moving averages
    df["EMA20"] = (
        df["Close"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    df["EMA50"] = (
        df["Close"]
        .ewm(span=50, adjust=False)
        .mean()
    )

    # RSI
    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    # Handle periods without losses
    df.loc[
        (avg_loss == 0) & (avg_gain > 0),
        "RSI"
    ] = 100

    df.loc[
        (avg_loss == 0) & (avg_gain == 0),
        "RSI"
    ] = 50

    # Volume
    df["AvgVolume20"] = (
        df["Volume"].rolling(20).mean()
    )

    df["VolumePct"] = (
        df["Volume"] /
        df["AvgVolume20"].replace(0, np.nan)
        * 100
    )

    # Previous 20-session high
    df["PreviousHigh20"] = (
        df["High"]
        .rolling(20)
        .max()
        .shift(1)
    )

    # Distance to breakout
    df["BreakoutDistancePct"] = (
        (
            df["PreviousHigh20"] - df["Close"]
        )
        / df["PreviousHigh20"].replace(0, np.nan)
        * 100
    )

    # Daily price change
    df["DailyChangePct"] = (
        df["Close"].pct_change() * 100
    )

    # Close location inside daily range
    daily_range = (
        df["High"] - df["Low"]
    ).replace(0, np.nan)

    df["CloseLocation"] = (
        (df["Close"] - df["Low"])
        / daily_range
        * 100
    )

    # Breakout
    df["Breakout"] = (
        df["Close"] > df["PreviousHigh20"]
    )

    return df


# =========================================================
# POTENTIAL ACCUMULATION DETECTION
# =========================================================

def detect_potential_accumulation(df):

    if df is None or len(df) < 25:
        return False

    recent = df.tail(5)

    required_columns = [
        "VolumePct",
        "CloseLocation",
        "Close"
    ]

    if not all(
        column in recent.columns
        for column in required_columns
    ):
        return False

    if recent[required_columns].isna().any().any():
        return False

    high_volume_days = (
        recent["VolumePct"] >= 120
    ).sum()

    strong_close_days = (
        recent["CloseLocation"] >= 50
    ).sum()

    five_day_return = (
        recent["Close"].iloc[-1]
        / recent["Close"].iloc[0]
        - 1
    ) * 100

    potential_accumulation = (
        high_volume_days >= 3
        and strong_close_days >= 3
        and five_day_return >= -2
    )

    return bool(potential_accumulation)


# =========================================================
# STOCK ANALYSIS
# =========================================================

def analyze_stock(
    symbol,
    market,
    period,
    interval,
    min_volume,
    min_score
):

    try:

        df = download_stock_data(
            symbol=symbol,
            market=market,
            period=period,
            interval=interval
        )

        if df is None or df.empty:
            return None

        if len(df) < 55:
            return None

        df = calculate_indicators(df)

        latest = df.iloc[-1]

        required_values = [
            "Close",
            "EMA20",
            "EMA50",
            "RSI",
            "VolumePct",
            "PreviousHigh20",
            "BreakoutDistancePct",
            "DailyChangePct",
            "CloseLocation"
        ]

        for column in required_values:
            if pd.isna(latest[column]):
                return None

        price = float(latest["Close"])
        ema20 = float(latest["EMA20"])
        ema50 = float(latest["EMA50"])
        rsi = float(latest["RSI"])
        volume_pct = float(latest["VolumePct"])

        breakout_distance = float(
            latest["BreakoutDistancePct"]
        )

        daily_change = float(
            latest["DailyChangePct"]
        )

        close_location = float(
            latest["CloseLocation"]
        )

        breakout = bool(latest["Breakout"])

        # ---------------------------------------------
        # SCORE
        # ---------------------------------------------

        score = 0
        reasons = []

        if price > ema20:
            score += 15
            reasons.append("Price above EMA20")

        if ema20 > ema50:
            score += 20
            reasons.append("EMA20 above EMA50")

        if 50 <= rsi <= 70:
            score += 15
            reasons.append("RSI positive range")

        if volume_pct >= min_volume:
            score += 20
            reasons.append("Volume above threshold")

        if breakout:
            score += 30
            reasons.append("20-session breakout")

        # ---------------------------------------------
        # SIGNAL CLASSIFICATION
        # ---------------------------------------------

        signal = "NO SIGNAL"

        if breakout and score >= min_score:

            signal = "CONFIRMED BREAKOUT"

        elif (
            price > ema20
            and ema20 > ema50
            and volume_pct >= min_volume
            and score >= min_score
        ):

            signal = "EARLY SETUP"

        # ---------------------------------------------
        # POTENTIAL ACCUMULATION
        # ---------------------------------------------

        potential_accumulation = (
            detect_potential_accumulation(df)
        )

        # ---------------------------------------------
        # DATA STATUS
        # ---------------------------------------------

        data_status = get_data_status(df)

        last_date = str(df.index[-1].date())

        return {

            "Symbol": symbol,

            "Price": round(price, 3),

            "Daily Change %": round(
                daily_change, 2
            ),

            "EMA20": round(ema20, 3),

            "EMA50": round(ema50, 3),

            "RSI": round(rsi, 2),

            "Volume %": round(volume_pct, 2),

            "Breakout Distance %": round(
                breakout_distance, 2
            ),

            "Close Location %": round(
                close_location, 2
            ),

            "Signal Score": score,

            "Signal": signal,

            "Potential Accumulation":
                potential_accumulation,

            "Reasons": ", ".join(reasons),

            "Last Data": last_date,

            "Data Status": data_status["status"]

        }

    except Exception as error:

        return {
            "Symbol": symbol,
            "Error": str(error)
        }


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("SCAN SETTINGS")

market = st.sidebar.selectbox(
    "Market",
    [
        "NASDAQ",
        "NYSE",
        "TEL AVIV",
        "ALL MARKETS"
    ]
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    [
        "Daily",
        "Weekly"
    ]
)

min_volume = st.sidebar.slider(
    "Minimum Volume % of Average",
    min_value=50,
    max_value=300,
    value=100,
    step=10
)

min_score = st.sidebar.slider(
    "Minimum Signal Score",
    min_value=10,
    max_value=100,
    value=40,
    step=5
)


# =========================================================
# SYMBOL UNIVERSE
# =========================================================

st.subheader("Stock Universe")

if market == "TEL AVIV":

    default_symbols = "TEVA, LUMI, POLI"

elif market == "ALL MARKETS":

    default_symbols = (
        "AAPL, MSFT, NVDA, AMD, TSLA, "
        "TEVA, LUMI, POLI"
    )

else:

    default_symbols = (
        "AAPL, MSFT, NVDA, AMD, TSLA"
    )

symbols_input = st.text_area(
    "Enter stock symbols separated by commas",
    value=default_symbols,
    height=100
)

symbols = [
    item.strip().upper()
    for item in symbols_input.split(",")
    if item.strip()
]

# Remove duplicates while preserving order
symbols = list(dict.fromkeys(symbols))


# =========================================================
# TIMEFRAME SETTINGS
# =========================================================

if timeframe == "Daily":

    period = "2y"
    interval = "1d"

else:

    period = "5y"
    interval = "1wk"


# =========================================================
# SCAN BUTTON
# =========================================================

run_scan = st.button(
    "🚀 RUN SMART MONEY SCAN",
    type="primary",
    use_container_width=True
)


# =========================================================
# RUN SCAN
# =========================================================

if run_scan:

    if not symbols:

        st.warning("Please enter at least one stock symbol.")

    else:

        results = []

        progress = st.progress(0)

        status_text = st.empty()

        for index, symbol in enumerate(symbols):

            status_text.write(
                f"Scanning {symbol}..."
            )

            # For All Markets, identify Tel Aviv symbols
            # by the .TA suffix.
            if market == "ALL MARKETS":

                if symbol.endswith(".TA"):
                    stock_market = "TEL AVIV"
                else:
                    stock_market = "NASDAQ"

            else:

                stock_market = market

            result = analyze_stock(
                symbol=symbol,
                market=stock_market,
                period=period,
                interval=interval,
                min_volume=min_volume,
                min_score=min_score
            )

            if result is not None:
                results.append(result)

            progress.progress(
                (index + 1) / len(symbols)
            )

        status_text.empty()
        progress.empty()

        st.session_state["scan_results"] = results

        st.success(
            f"Scan completed. "
            f"{len(results)} stocks processed."
        )


# =========================================================
# RESULTS
# =========================================================

if "scan_results" in st.session_state:

    results = st.session_state["scan_results"]

    valid_results = [
        item for item in results
        if "Error" not in item
    ]

    errors = [
        item for item in results
        if "Error" in item
    ]

    if valid_results:

        df_results = pd.DataFrame(valid_results)

        # ---------------------------------------------
        # SUMMARY METRICS
        # ---------------------------------------------

        total_stocks = len(df_results)

        breakout_count = (
            df_results["Signal"]
            == "CONFIRMED BREAKOUT"
        ).sum()

        early_count = (
            df_results["Signal"]
            == "EARLY SETUP"
        ).sum()

        accumulation_count = (
            df_results["Potential Accumulation"]
        ).sum()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Stocks Scanned",
            total_stocks
        )

        col2.metric(
            "Early Setups",
            int(early_count)
        )

        col3.metric(
            "Confirmed Breakouts",
            int(breakout_count)
        )

        col4.metric(
            "Potential Accumulation",
            int(accumulation_count)
        )

        st.divider()

        # ---------------------------------------------
        # TABS
        # ---------------------------------------------

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                "All Results",
                "Early Setup",
                "Breakouts",
                "Smart Money",
                "Diagnostics"
            ]
        )

        # ---------------------------------------------
        # ALL RESULTS
        # ---------------------------------------------

        with tab1:

            st.subheader("All Scanned Stocks")

            st.dataframe(
                df_results,
                use_container_width=True,
                hide_index=True
            )

        # ---------------------------------------------
        # EARLY SETUPS
        # ---------------------------------------------

        with tab2:

            st.subheader("Early Setup Candidates")

            early_df = df_results[
                df_results["Signal"] == "EARLY SETUP"
            ]

            if early_df.empty:

                st.info("No Early Setup candidates found.")

            else:

                st.dataframe(
                    early_df,
                    use_container_width=True,
                    hide_index=True
                )

        # ---------------------------------------------
        # CONFIRMED BREAKOUTS
        # ---------------------------------------------

        with tab3:

            st.subheader("Confirmed Breakouts")

            breakout_df = df_results[
                df_results["Signal"]
                == "CONFIRMED BREAKOUT"
            ]

            if breakout_df.empty:

                st.info("No confirmed breakouts found.")

            else:

                st.dataframe(
                    breakout_df,
                    use_container_width=True,
                    hide_index=True
                )

        # ---------------------------------------------
        # POTENTIAL ACCUMULATION
        # ---------------------------------------------

        with tab4:

            st.subheader("Potential Accumulation")

            st.caption(
                "Preliminary technical heuristic. "
                "This does not confirm institutional buying."
            )

            accumulation_df = df_results[
                df_results["Potential Accumulation"]
            ]

            if accumulation_df.empty:

                st.info(
                    "No potential accumulation patterns found."
                )

            else:

                st.dataframe(
                    accumulation_df,
                    use_container_width=True,
                    hide_index=True
                )

        # ---------------------------------------------
        # DIAGNOSTICS
        # ---------------------------------------------

        with tab5:

            st.subheader("Technical Diagnostics")

            diagnostic_columns = [
                "Symbol",
                "Price",
                "Daily Change %",
                "EMA20",
                "EMA50",
                "RSI",
                "Volume %",
                "Breakout Distance %",
                "Close Location %",
                "Signal Score",
                "Reasons",
                "Last Data"
            ]

            st.dataframe(
                df_results[diagnostic_columns],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("""
            **How to read the diagnostics**

            - EMA20 / EMA50: Short and medium-term trend.
            - RSI: Momentum indicator.
            - Volume %: Latest volume relative to its 20-session average.
            - Breakout Distance %: Distance from the previous 20-session high.
            - Close Location %: Where the stock closed within its daily range.
            - Signal Score: Technical score based on the rules above.
            """)

        # ---------------------------------------------
        # DOWNLOAD RESULTS
        # ---------------------------------------------

        csv_data = df_results.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="📥 Download Scan Results CSV",
            data=csv_data,
            file_name="smart_money_scan_results.csv",
            mime="text/csv"
        )

    else:

        st.warning(
            "No valid stock data was returned."
        )

    # ---------------------------------------------
    # ERRORS
    # ---------------------------------------------

    if errors:

        with st.expander("Stocks with data errors"):

            st.dataframe(
                pd.DataFrame(errors),
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "SMART MONEY SCANNER PRO | "
    "Data source: Yahoo Finance | "
    "Historical and delayed data may be used. "
    "This tool is for research and educational purposes."
)

st.caption(
    "Last application update: "
    + datetime.now().strftime("%Y-%m-%d %H:%M")
)
