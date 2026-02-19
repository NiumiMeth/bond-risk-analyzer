import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ==================== PAGE SETUP ====================
st.set_page_config(layout="wide", page_title="Treasury Bond Risk Dashboard")
st.title("🏦 Treasury Bond Risk & Yield Shock Engine")

# ==================== FILE UPLOAD ====================
uploaded_file = st.file_uploader(
    "Upload Bond Portfolio File (Excel or CSV)", 
    type=["xlsx", "csv"]
)

if uploaded_file is not None:
    with st.spinner("Processing portfolio..."):

        # Load file
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file)
        else:
            df_raw = pd.read_excel(uploaded_file)

        # ==================== COLUMN MAPPING ====================
        canonical_columns = {
            "isin": "ISIN",
            "initial inv date": "Initial Inv Date",
            "maturity date": "Maturity Date",
            "coupon": "Coupon",
            "maturity value": "Maturity Value",
            "ytm": "YTM"
        }

        # Clean headers
        df_raw.columns = [str(col).strip().lower() for col in df_raw.columns]
        df_raw.rename(columns=canonical_columns, inplace=True)
        existing_cols = [v for v in canonical_columns.values() if v in df_raw.columns]
        df = df_raw[existing_cols].copy()

        essential = ["ISIN", "Maturity Date", "Coupon", "Maturity Value", "YTM"]
        missing = [c for c in essential if c not in df.columns]
        if missing:
            st.error(f"Uploaded file is missing required columns: {', '.join(missing)}")
            st.stop()

        # ==================== DATA CLEANING ====================
        df["Maturity Value"] = pd.to_numeric(df["Maturity Value"].astype(str).str.replace(",", ""), errors="coerce")
        df["Coupon"] = pd.to_numeric(df["Coupon"].astype(str).str.replace("%", ""), errors="coerce") / 100
        df["YTM"] = pd.to_numeric(df["YTM"], errors="coerce") / 100
        df["Maturity Date"] = pd.to_datetime(df["Maturity Date"], errors="coerce")
        df = df.dropna(subset=essential)

        today = datetime.today()
        df["Years_to_Maturity"] = (df["Maturity Date"] - today).dt.days / 365
        df = df[df["Years_to_Maturity"] > 0]

        # ==================== BOND PRICING FUNCTIONS ====================
        def bond_price(face, coupon_rate, ytm, years):
            coupon = face * coupon_rate
            periods = int(np.ceil(years))
            price = sum([coupon / ((1 + ytm) ** t) for t in range(1, periods + 1)])
            price += face / ((1 + ytm) ** periods)
            return price

        def macaulay_duration(face, coupon_rate, ytm, years):
            coupon = face * coupon_rate
            periods = int(np.ceil(years))
            price = bond_price(face, coupon_rate, ytm, years)
            weighted_sum = sum([t * (coupon + (face if t == periods else 0)) / ((1 + ytm) ** t) for t in range(1, periods + 1)])
            return weighted_sum / price

        def convexity(face, coupon_rate, ytm, years):
            coupon = face * coupon_rate
            periods = int(np.ceil(years))
            price = bond_price(face, coupon_rate, ytm, years)
            conv_sum = sum([(coupon + (face if t == periods else 0)) * t * (t + 1) / ((1 + ytm) ** (t + 2)) for t in range(1, periods + 1)])
            return conv_sum / price

        # ==================== BASE CALCULATIONS ====================
        df["Price"] = df.apply(lambda row: bond_price(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years_to_Maturity"]), axis=1)
        df["Market Value"] = df["Price"]
        df["Macaulay Duration"] = df.apply(lambda row: macaulay_duration(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years_to_Maturity"]), axis=1)
        df["Modified Duration"] = df["Macaulay Duration"] / (1 + df["YTM"])
        df["Convexity"] = df.apply(lambda row: convexity(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years_to_Maturity"]), axis=1)
        df["DV01"] = df["Modified Duration"] * df["Market Value"] * 0.0001

        # ==================== YIELD SHOCK ====================
        st.sidebar.header("Yield Shock Settings")
        shock_bps = st.sidebar.slider("Parallel Yield Shock (bps)", -500, 500, 100, step=10)
        shock = shock_bps / 10000  # convert bps to decimal

        df["New_YTM"] = df["YTM"] + shock
        df["New Price"] = df.apply(lambda row: bond_price(row["Maturity Value"], row["Coupon"], row["New_YTM"], row["Years_to_Maturity"]), axis=1)
        df["Price Change"] = df["New Price"] - df["Price"]
        df["P/L Impact"] = df["Price Change"]

        # ==================== PORTFOLIO METRICS ====================
        total_mv = df["Market Value"].sum()
        total_pl = df["P/L Impact"].sum()
        weighted_duration = (df["Modified Duration"] * df["Market Value"]).sum() / total_mv
        total_dv01 = df["DV01"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Market Value", f"{total_mv:,.2f}")
        col2.metric("Total P/L Impact", f"{total_pl:,.2f}")
        col3.metric("Weighted Duration", f"{weighted_duration:.2f}")
        col4.metric("Portfolio DV01", f"{total_dv01:,.2f}")

        # ==================== AFFECTED ISINS ====================
        st.subheader("🔎 ISINs Affected by Yield Shock")
        # Color coding for gains/losses
        def color_price(val):
            color = 'green' if val >= 0 else 'red'
            return f'color: {color}'
        affected = df[["ISIN","Market Value","Modified Duration","DV01","Price Change","P/L Impact"]].sort_values("P/L Impact", ascending=True)
        st.dataframe(affected.style.applymap(color_price, subset=["Price Change","P/L Impact"]), use_container_width=True)

        # ==================== FULL PORTFOLIO VIEW ====================
        st.subheader("📘 Full Portfolio Risk Table")
        st.dataframe(df, use_container_width=True)

        # ==================== DOWNLOAD ====================
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Risk Report", csv, "bond_risk_report.csv", "text/csv")

else:
    st.info("Upload a portfolio file to begin analysis.")
