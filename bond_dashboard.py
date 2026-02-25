import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go

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

        # ==================== SPOT DATE ====================
        spot_date = st.date_input("Spot / Settlement Date", value=datetime.today())
        spot_date = pd.to_datetime(spot_date)
        df["Years to Maturity"] = (df["Maturity Date"] - spot_date).dt.days / 365
        df = df[df["Years to Maturity"] > 0]

        # ==================== ISIN FILTER ====================
        st.sidebar.markdown("**Filter by ISIN**")
        isin_options = df["ISIN"].unique().tolist()
        selected_isins = st.sidebar.multiselect("Select ISINs to view", isin_options, default=isin_options)
        df = df[df["ISIN"].isin(selected_isins)]

        # ==================== TABS FOR ORGANIZATION ====================
        tab1, tab2, tab3 = st.tabs(["Portfolio", "Risk Metrics", "Visualizations"])


        with tab1:
            st.subheader("📘 Full Portfolio Table")
            currency_cols = ["Market Value", "Maturity Value", "Price", "New Price", "ISIN_Specific_Market Value"]
            df_display = df.copy()
            for col in currency_cols:
                if col in df_display.columns:
                    df_display[col] = df_display[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
            st.dataframe(df_display, use_container_width=True)
            st.markdown("ℹ️ **Portfolio Table:** Shows all bonds in your portfolio. Use sidebar to filter by ISIN. Currency columns are formatted for readability.")

        # The rest of your calculations and visualizations should be placed inside tab2 and tab3 as shown in the previous message.

        # ==================== BOND PRICING FUNCTIONS ====================
        def bond_price(face, coupon_rate, ytm, years, freq=2):
            """Semi-annual pricing with fractional periods"""
            periods = years * freq
            coupon = face * coupon_rate / freq
            price = sum([coupon / ((1 + ytm/freq) ** t) for t in range(1, int(np.floor(periods)) + 1)])
            fractional = periods - int(np.floor(periods))
            if fractional > 0:
                price += (coupon + face) / ((1 + ytm/freq) ** (periods))
            else:
                price += face / ((1 + ytm/freq) ** int(periods))
            return price

        def macaulay_duration(face, coupon_rate, ytm, years, freq=2):
            periods = years * freq
            coupon = face * coupon_rate / freq
            price = bond_price(face, coupon_rate, ytm, years, freq)
            weighted_sum = sum([t * coupon / ((1 + ytm/freq) ** t) for t in range(1, int(np.floor(periods)) + 1)])
            weighted_sum += int(periods) * (coupon + face) / ((1 + ytm/freq) ** int(periods))
            return weighted_sum / price

        def modified_duration(face, coupon_rate, ytm, years, freq=2):
            return macaulay_duration(face, coupon_rate, ytm, years, freq) / (1 + ytm/freq)

        def convexity(face, coupon_rate, ytm, years, freq=2):
            periods = years * freq
            coupon = face * coupon_rate / freq
            price = bond_price(face, coupon_rate, ytm, years, freq)
            conv_sum = sum([(t * (t + 1)) * coupon / ((1 + ytm/freq) ** (t + 2)) for t in range(1, int(np.floor(periods)) + 1)])
            conv_sum += (int(periods) * (int(periods) + 1)) * (coupon + face) / ((1 + ytm/freq) ** (int(periods) + 2))
            return conv_sum / price

        # ==================== BASE CALCULATIONS ====================
        df["Price"] = df.apply(lambda row: bond_price(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years to Maturity"]), axis=1)
        df["Market Value"] = df["Price"]  # no Quantity
        df["Macaulay Duration"] = df.apply(lambda row: macaulay_duration(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years to Maturity"]), axis=1)
        df["Modified Duration"] = df.apply(lambda row: modified_duration(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years to Maturity"]), axis=1)
        df["Convexity"] = df.apply(lambda row: convexity(row["Maturity Value"], row["Coupon"], row["YTM"], row["Years to Maturity"]), axis=1)
        df["DV01"] = df["Modified Duration"] * df["Market Value"] * 0.0001

        # ==================== YIELD SHOCK ====================
        st.sidebar.header("Yield Shock Settings")
        # Numeric input for % shock
        shock_pct = st.sidebar.number_input("Parallel Yield Shock (%)", value=0.0, step=0.1)
        shock = shock_pct / 100

        df["New_YTM"] = df["YTM"] + shock
        df["New Price"] = df.apply(lambda row: bond_price(row["Maturity Value"], row["Coupon"], row["New_YTM"], row["Years to Maturity"]), axis=1)
        df["Price Change"] = df["New Price"] - df["Price"]
        df["P/L Impact"] = df["Price Change"]  # no Quantity

        # Duration-based approximation
        df["Duration Approx P/L"] = -df["Modified Duration"] * df["Market Value"] * shock

        # Contribution to P/L
        total_pl = df["P/L Impact"].sum()
        df["% Contribution to P/L"] = df["P/L Impact"] / total_pl * 100 if total_pl != 0 else 0

        # ==================== ISIN-SPECIFIC YIELD SHOCK ====================
        st.sidebar.header("ISIN-Specific Yield Shock Settings")

        # Get unique ISINs
        unique_isins = df["ISIN"].unique()

        # Create a dictionary to store ISIN-specific shocks
        isin_shocks = {}
        for isin in unique_isins:
            isin_shocks[isin] = st.sidebar.number_input(f"Yield Shock for ISIN {isin} (%)", value=0.0, step=0.1)

        # Apply ISIN-specific shocks
        def apply_isin_shock(row):
            isin = row["ISIN"]
            specific_shock = isin_shocks.get(isin, 0.0) / 100  # Convert to decimal
            return row["YTM"] + specific_shock

        df["ISIN_Specific_YTM"] = df.apply(apply_isin_shock, axis=1)
        df["ISIN_Specific_Price"] = df.apply(lambda row: bond_price(row["Maturity Value"], row["Coupon"], row["ISIN_Specific_YTM"], row["Years to Maturity"]), axis=1)
        df["ISIN_Specific_Price Change"] = df["ISIN_Specific_Price"] - df["Price"]
        df["ISIN_Specific_P/L Impact"] = df["ISIN_Specific_Price Change"]  # no Quantity

        # Add Maturity Date to ISIN-Specific DataFrame
        df["ISIN_Specific_Maturity Date"] = df["Maturity Date"]

        # Extend ISIN-Specific DataFrame with additional columns from Full Portfolio Risk Table
        df["ISIN_Specific_Market Value"] = df["Market Value"]
        df["ISIN_Specific_Modified Duration"] = df["Modified Duration"]
        df["ISIN_Specific_DV01"] = df["DV01"]
        df["ISIN_Specific_% Contribution to P/L"] = df["ISIN_Specific_P/L Impact"] / total_pl * 100 if total_pl != 0 else 0
        df["ISIN_Specific_Duration Approx P/L"] = -df["ISIN_Specific_Modified Duration"] * df["ISIN_Specific_Market Value"] * shock

        # Debugging: Log ISIN-specific shocks and recalculated prices
        st.write("ISIN-Specific Shocks:", isin_shocks)
        st.write("Updated DataFrame with ISIN-Specific YTM, Prices, and Maturity Date:")
        st.dataframe(df[["ISIN", "YTM", "ISIN_Specific_YTM", "Price", "ISIN_Specific_Price", "ISIN_Specific_Price Change", 
            "ISIN_Specific_Market Value", "ISIN_Specific_Modified Duration", "ISIN_Specific_DV01", 
            "ISIN_Specific_% Contribution to P/L", "ISIN_Specific_Duration Approx P/L", "ISIN_Specific_Maturity Date"]])


        # Add ISIN-specific yield curve visualization
        st.subheader("📈 ISIN-Specific Yield Curve Visualization")
        fig_isin_yield = go.Figure()

        # Original yield curve
        fig_isin_yield.add_trace(go.Scatter(
            x=df["Years to Maturity"],
            y=df["YTM"] * 100,
            mode='lines+markers',
            name='Original YTM',
            line=dict(color='blue', width=2)
        ))

        # ISIN-specific shocked yield curve
        fig_isin_yield.add_trace(go.Scatter(
            x=df["Years to Maturity"],
            y=df["ISIN_Specific_YTM"] * 100,
            mode='lines+markers',
            name='ISIN-Specific YTM',
            line=dict(color='green', width=2, dash='dot')
        ))

        fig_isin_yield.update_layout(
            title='ISIN-Specific Yield Curve',
            xaxis_title='Years to Maturity',
            yaxis_title='Yield (%)',
            template='plotly_white'
        )

        st.plotly_chart(fig_isin_yield, use_container_width=True)

        # ==================== TOP 5 MOST SENSITIVE ISINS (ISIN-Specific Shock) ====================
        st.subheader("🔥 Top 5 Most Sensitive ISINs (ISIN-Specific Yield Shock)")
        top_isin_specific = df[["ISIN", "ISIN_Specific_P/L Impact", "ISIN_Specific_Price Change", "ISIN_Specific_Market Value", "ISIN_Specific_Modified Duration", "ISIN_Specific_DV01"]].copy()
        for col in ["ISIN_Specific_P/L Impact", "ISIN_Specific_Price Change", "ISIN_Specific_Market Value", "ISIN_Specific_DV01"]:
            if col in top_isin_specific.columns:
                top_isin_specific[col] = top_isin_specific[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
        top_isin_specific = top_isin_specific.reindex(top_isin_specific["ISIN_Specific_P/L Impact"].apply(lambda x: float(x.replace(",", "")) if x else 0).abs().sort_values(ascending=False).index).head(5)
        st.table(top_isin_specific)
        st.bar_chart(top_isin_specific.set_index("ISIN")["ISIN_Specific_P/L Impact"].apply(lambda x: float(x.replace(",", "")) if x else 0))

        # ==================== PORTFOLIO METRICS ====================
        total_mv = df["Market Value"].sum()
        weighted_duration = (df["Modified Duration"] * df["Market Value"]).sum() / total_mv
        total_dv01 = df["DV01"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Market Value", f"{total_mv:,.2f}")
        col2.metric("Total P/L Impact", f"{total_pl:,.2f}")
        col3.metric("Weighted Duration", f"{weighted_duration:.2f}")
        col4.metric("Portfolio DV01", f"{total_dv01:,.2f}")


        # ==================== TOP 5 MOST SENSITIVE ISINS ====================
        st.subheader("🔥 Top 5 Most Sensitive ISINs (by P/L Impact)")
        top_sensitive = df[["ISIN", "Market Value", "Modified Duration", "DV01", "Price Change", "P/L Impact"]].copy()
        for col in ["Market Value", "Price Change", "P/L Impact", "DV01"]:
            if col in top_sensitive.columns:
                top_sensitive[col] = top_sensitive[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
        top_sensitive = top_sensitive.reindex(top_sensitive["P/L Impact"].apply(lambda x: float(x.replace(",", "")) if x else 0).abs().sort_values(ascending=False).index).head(5)
        st.table(top_sensitive)
        st.bar_chart(top_sensitive.set_index("ISIN")["P/L Impact"].apply(lambda x: float(x.replace(",", "")) if x else 0))

        # ==================== AFFECTED ISINS ====================
        st.subheader("🔎 ISINs Affected by Yield Shock")
        affected = df[["ISIN","Market Value","Modified Duration","DV01","Price Change","P/L Impact","% Contribution to P/L","Duration Approx P/L"]].sort_values("P/L Impact", ascending=True)
        def color_price(val):
            color = 'green' if val >= 0 else 'red'
            return f'color: {color}'
        st.dataframe(affected.style.applymap(color_price, subset=["Price Change","P/L Impact"]), use_container_width=True)

        # ==================== FULL PORTFOLIO VIEW ====================
        st.subheader("📘 Full Portfolio Risk Table")
        st.dataframe(df, use_container_width=True)

        # ==================== DOWNLOAD ====================
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Risk Report", csv, "bond_risk_report.csv", "text/csv")

        # ==================== YIELD CURVE VISUALIZATION ====================
        st.subheader("📈 Yield Curve Visualization")
        fig_yield = go.Figure()

        # Original yield curve
        fig_yield.add_trace(go.Scatter(
            x=df["Years to Maturity"],
            y=df["YTM"] * 100,
            mode='lines+markers',
            name='Original YTM',
            line=dict(color='blue', width=2)
        ))

        # Shocked yield curve
        fig_yield.add_trace(go.Scatter(
            x=df["Years to Maturity"],
            y=df["New_YTM"] * 100,
            mode='lines+markers',
            name=f'YTM after {shock_pct:.2f}% shock',
            line=dict(color='red', width=2, dash='dash')
        ))

        fig_yield.update_layout(
            title='Yield Curve',
            xaxis_title='Years to Maturity',
            yaxis_title='Yield (%)',
            template='plotly_white'
        )

        st.plotly_chart(fig_yield, use_container_width=True)

else:
    st.info("Upload a portfolio file to begin analysis.")