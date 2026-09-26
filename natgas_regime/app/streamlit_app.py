from __future__ import annotations
from pathlib import Path
import plotly.express as px
import streamlit as st
from natgas_regime.workflow import run_backtest_from_config

DEFAULT_CONFIG = Path("config/natgas_event_outright_v1.yaml")

st.set_page_config(page_title="Nat Gas Regime", layout="wide")
st.title("Nat Gas Regime Strategy")

config_path = st.sidebar.text_input("Strategy config", str(DEFAULT_CONFIG))

backtest, metrics = run_backtest_from_config(config_path)
latest = backtest.dropna(subset=["ng1_settle"]).iloc[-1]

cols = st.columns(5)
cols[0].metric("Equity", f"${metrics['end_equity']:,.0f}")
cols[1].metric("CAGR", f"{metrics['cagr']:.2%}")
cols[2].metric("Sharpe", f"{metrics['sharpe']:.2f}")
cols[3].metric("Max DD", f"{metrics['max_drawdown']:.2%}")
cols[4].metric("Current Pos", f"{latest['signed_contracts']:.0f}")

regime_cols = st.columns(5)
regime_cols[0].metric("Season", str(latest["season"]))
regime_cols[1].metric("Storage z", f"{latest['storage_z']:.2f}")
regime_cols[2].metric("Slope", f"{latest['slope']:.2%}")
regime_cols[3].metric("RV20", f"{latest['rv20']:.2%}")
regime_cols[4].metric("Risk-off", "Yes" if latest["riskoff"] else "No")

tab_equity, tab_prices, tab_features, tab_data = st.tabs(["Backtest", "Prices", "Features", "Data"])

with tab_equity:
    st.plotly_chart(px.line(backtest, x="date", y="equity", title="Equity Curve"), use_container_width=True)
    st.plotly_chart(
        px.area(backtest, x="date", y="drawdown", title="Drawdown"),
        use_container_width=True,
    )
    st.plotly_chart(
        px.line(backtest, x="date", y="signed_contracts", title="Signed Contracts"),
        use_container_width=True,
    )

with tab_prices:
    price_frame = backtest.rename(
        columns={
            "ng1_settle": "NG1",
            "ng2_settle": "NG2",
        }
    )
    st.plotly_chart(
        px.line(
            price_frame,
            x="date",
            y=["NG1", "NG2"],
            title="NG1 / NG2 Continuous Futures",
            labels={"value": "Price", "variable": "Series"},
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        px.line(backtest, x="date", y="spread_settle", title="NG1 - NG2 Spread"),
        use_container_width=True,
    )

with tab_features:
    st.plotly_chart(
        px.line(backtest, x="date", y=["storage_z", "slope", "rv20"], title="Feature History"),
        use_container_width=True,
    )
    season_perf = (
        backtest.groupby("season", dropna=False)["daily_return"]
        .agg(["count", "mean", "std"])
        .reset_index()
    )
    st.dataframe(season_perf, use_container_width=True)

with tab_data:
    st.dataframe(backtest.tail(250), use_container_width=True)
