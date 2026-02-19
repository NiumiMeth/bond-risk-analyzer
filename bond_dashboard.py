import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🏦 Treasury Bond Risk & Yield Shock Engine")

# ==========================================================
# FILE UPLOAD (Excel or CSV)
# ==========================================================

uploaded_file = st.file_uploader(
    "Upload Bond Portfolio File (Excel or CSV)", 
    type=["xlsx", "csv"]
)

if uploaded_file is not None:

    with st.spinner("Processing portfolio..."):

        # Detect file type
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file)
        else:  # Excel
            df_raw = pd.read_excel(uploaded_file)


        # ==========================================================
        # FLEXIBLE COLUMN MAPPING
        # ==========================================================

        # Define canonical column names
        canonical_columns = {
            "isin": "ISIN",
            "initial inv date": "Initial Inv Date",
            "maturity date": "Maturity Date",
            "coupon": "Coupon",
            "maturity value": "Maturity Value",
            "ytm": "YTM"
        }

        # Clean CSV/Excel columns: lowercase + strip spaces
        df_raw.columns = [str(col).strip().lower() for col in df_raw.columns]

        # Map to canonical names
        df_raw.rename(columns=canonical_columns, inplace=True)

        # Keep only columns that exist after mapping
        existing_cols = [v for v in canonical_columns.values() if v in df_raw.columns]
        df = df_raw[existing_cols].copy()

        if "Maturity Value" not in df.columns or "Coupon" not in df.columns or "YTM" not in df.columns:
            st.error("Uploaded file is missing required columns: 'Maturity Value', 'Coupon', or 'YTM'. Please check your file.")
            st.stop()

        # ==========================================================
        # CLEANING & STANDARDIZATION
        # ==========================================================

        required_columns = [
            "ISIN",
            "Initial Inv Date",
            "Maturity Date",
            "Coupon",
            "Maturity Value",
            "YTM"
        ]

        df = df[required_columns].copy()
        df = df[df["ISIN"].notna()]

        # Clean Maturity Value
        df["Maturity Value"] = (
            df["Maturity Value"]
            .astype(str)
            .str.replace(",", "")
            .str.strip()
        )
        df["Maturity Value"] = pd.to_numeric(df["Maturity Value"], errors="coerce")

        # Clean Coupon
        df["Coupon"] = (
            df["Coupon"]
            .astype(str)
            .str.replace("%", "")
            .str.strip()
        )
        df["Coupon"] = pd.to_numeric(df["Coupon"], errors="coerce") / 100

        # Clean YTM
        df["YTM"] = pd.to_numeric(df["YTM"], errors="coerce") / 100

        # Convert Dates
        df["Maturity Date"] = pd.to_datetime(df["Maturity Date"], errors="coerce")

        df = df.dropna(subset=["Maturity Value", "Coupon", "YTM", "Maturity Date"])

        today = datetime.today()
        df["Years_to_Maturity"] = (df["Maturity Date"] - today).dt.days / 365
        df = df[df["Years_to_Maturity"] > 0]

        # ==========================================================
        # BOND PRICING FUNCTIONS (ANNUAL COUPON)
        # ==========================================================

        def bond_price(face, coupon_rate, ytm, years):
            coupon = face * coupon_rate
            periods = int(np.ceil(years))
            price = 0

            for t in range(1, periods + 1):
                price += coupon / ((1 + ytm) ** t)

            price += face / ((1 + ytm) ** periods)
            return price


        def macaulay_duration(face, coupon_rate, ytm, years):
            coupon = face * coupon_rate
            periods = int(np.ceil(years))
            price = bond_price(face, coupon_rate, ytm, years)

            weighted_sum = 0

            for t in range(1, periods + 1):
                cashflow = coupon
                if t == periods:
                    cashflow += face

                weighted_sum += t * cashflow / ((1 + ytm) ** t)

            return weighted_sum / price


        def convexity(face, coupon_rate, ytm, years):
            coupon = face * coupon_rate
            periods = int(np.ceil(years))
            price = bond_price(face, coupon_rate, ytm, years)

            convex_sum = 0

            for t in range(1, periods + 1):
                cashflow = coupon
                if t == periods:
                    cashflow += face

                convex_sum += cashflow * t * (t + 1) / ((1 + ytm) ** (t + 2))

            return convex_sum / price

        # ==========================================================
        # CALCULATIONS
        # ==========================================================

        prices = []
        durations = []
        convexities = []

        for _, row in df.iterrows():

            price = bond_price(
                row["Maturity Value"],
                row["Coupon"],
                row["YTM"],
                row["Years_to_Maturity"]
            )

            dur = macaulay_duration(
                row["Maturity Value"],
                row["Coupon"],
                row["YTM"],
                row["Years_to_Maturity"]
            )

            conv = convexity(
                row["Maturity Value"],
                row["Coupon"],
                row["YTM"],
                row["Years_to_Maturity"]
            )

            prices.append(price)
            durations.append(dur)
            convexities.append(conv)

        df["Price"] = prices
        df["Market Value"] = df["Price"]
        df["Macaulay Duration"] = durations
        df["Modified Duration"] = df["Macaulay Duration"] / (1 + df["YTM"])
        df["Convexity"] = convexities
        df["DV01"] = df["Modified Duration"] * df["Market Value"] * 0.0001

        # ==========================================================
        # YIELD SHOCK
        # ==========================================================

        st.sidebar.header("Yield Shock Settings")
        shock_bps = st.sidebar.slider("Parallel Yield Shock (bps)", -500, 500, 100)
        shock = shock_bps / 10000

        df["New_YTM"] = df["YTM"] + shock

        new_prices = []

        for _, row in df.iterrows():
            new_price = bond_price(
                row["Maturity Value"],
                row["Coupon"],
                row["New_YTM"],
                row["Years_to_Maturity"]
            )
            new_prices.append(new_price)

        df["New Price"] = new_prices
        df["Price Change"] = df["New Price"] - df["Price"]
        df["P/L Impact"] = df["Price Change"]

        # ==========================================================
        # PORTFOLIO METRICS
        # ==========================================================

        total_mv = df["Market Value"].sum()
        total_pl = df["P/L Impact"].sum()
        weighted_duration = (df["Modified Duration"] * df["Market Value"]).sum() / total_mv
        total_dv01 = df["DV01"].sum()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Market Value", f"{total_mv:,.2f}")
        col2.metric("Total P/L Impact", f"{total_pl:,.2f}")
        col3.metric("Weighted Duration", f"{weighted_duration:.2f}")
        col4.metric("Portfolio DV01", f"{total_dv01:,.2f}")

        # ==========================================================
        # AFFECTED ISINS
        # ==========================================================

        st.subheader("🔎 ISINs Affected by Yield Shock")

        affected = df[[
            "ISIN",
            "Market Value",
            "Modified Duration",
            "DV01",
            "Price Change",
            "P/L Impact"
        ]].sort_values("P/L Impact")

        st.dataframe(affected, use_container_width=True)

        # ==========================================================
        # FULL PORTFOLIO VIEW
        # ==========================================================

        st.subheader("📘 Full Portfolio Risk Table")
        st.dataframe(df, use_container_width=True)

        # ==========================================================
        # DOWNLOAD RESULTS
        # ==========================================================

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Risk Report",
            csv,
            "bond_risk_report.csv",
            "text/csv"
        )

else:
    st.info("Upload a portfolio file to begin analysis.")
