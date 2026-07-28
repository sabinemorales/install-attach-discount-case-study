"""
app.py
Aurora Install Attach & Discount Leakage - interactive dashboard + AI copilot.
A live companion to the static case study in this same repository.
"""

import os
import streamlit as st
import pandas as pd
from analysis import run_full_analysis
from ai_engine import generate_executive_briefing, generate_key_findings, generate_recommended_actions, chat_with_data

st.set_page_config(page_title="Aurora Install Attach & Discount Leakage", layout="wide")

st.title("Aurora Install Attach & Discount Leakage")
st.caption("A live, interactive companion to the static case study — fully synthetic company and data.")

# --- Startup checks ---
if not os.getenv("ANTHROPIC_API_KEY"):
    st.error(
        "No Anthropic API key found. Create a `.env` file in this project's root folder containing:\n\n"
        "`ANTHROPIC_API_KEY=your_key_here`\n\nGet a key at https://console.anthropic.com/settings/keys"
    )
    st.stop()


@st.cache_data
def get_analysis():
    return run_full_analysis()

with st.spinner("Loading synthetic dataset and running analysis..."):
    r = get_analysis()

# --- Executive Briefing ---
st.header("Executive Briefing")
if st.button("Generate Today's Briefing"):
    with st.spinner("Analyzing..."):
        st.markdown(generate_executive_briefing(r))

# --- Key Findings ---
st.header("Key Findings (Root Cause)")
if st.button("Investigate Anomalies"):
    with st.spinner("Digging into the data..."):
        st.markdown(generate_key_findings(r))

# --- Recommended Actions ---
st.header("Recommended Actions")
if st.button("Get This Week's Priorities"):
    with st.spinner("Prioritizing..."):
        st.markdown(generate_recommended_actions(r))

# --- Interactive Chat ---
st.header("Ask a Question")
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
user_question = st.chat_input("Ask anything about this data...")
if user_question:
    with st.chat_message("user"):
        st.markdown(user_question)
    with st.spinner("Thinking..."):
        answer = chat_with_data(r, st.session_state.chat_history, user_question)
    with st.chat_message("assistant"):
        st.markdown(answer)
    st.session_state.chat_history.append({"role": "user", "content": user_question})
    st.session_state.chat_history.append({"role": "assistant", "content": answer})

# --- Dashboard tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Attach Rate", "Discount Leakage", "SKU Analysis", "Cost & Estimation"]
)

with tab1:
    st.subheader("Portfolio Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("True Attach Rate", f"{r['true_rate']*100:.1f}%")
    col2.metric("Naive Attach Rate (miscounted)", f"{r['naive_rate']*100:.1f}%")
    col3.metric("Leakage vs 40% Cap", f"${r['total_leakage_cap']:,.0f}")
    col4.metric("Leakage vs 15% Target", f"${r['total_leakage_target']:,.0f}")
    st.info(
        f"**The category trap:** including the out-of-scope SKU (AR201#G1) inflates attach rate from "
        f"{r['true_rate']*100:.1f}% to {r['naive_rate']*100:.1f}% — a naive analysis would overcount attach "
        f"and undercount leakage by roughly the same margin."
    )
    st.warning(
        f"**Concentration:** {r['extreme_share_deals']*100:.1f}% of install deals exceed 80% discount, "
        f"accounting for {r['extreme_share_leakage']*100:.1f}% of total leakage. All are 5-year, Large-tier deals."
    )

with tab2:
    st.subheader("Attach Rate by Region")
    st.bar_chart(r["region_attach"]["attach_rate"])
    st.caption("Sorted ascending — regions on the left have the weakest install attach.")
    st.dataframe(r["region_attach"])

with tab3:
    st.subheader("Discount Leakage by Quarter: Cap vs Target Average")
    chart_df = r["leakage_by_q"][["leakage_cap", "leakage_target"]].rename(
        columns={"leakage_cap": "vs 40% Cap", "leakage_target": "vs 15% Target Avg"}
    )
    st.bar_chart(chart_df)
    st.dataframe(r["leakage_by_q"])

with tab4:
    st.subheader("Leakage by SKU")
    st.bar_chart(r["sku_by_sku"]["excess_cap"])
    st.dataframe(r["sku_by_sku"][["deals", "gross", "avg_discount_pct", "excess_cap"]])
    st.subheader("SKU Migration: Legacy (AR210) vs Replacement (AR215)")
    st.line_chart(r["migration"])
    st.caption("AR210 is marked retired in the SKU catalog, yet continues generating orders before volume shifts to AR215.")

with tab5:
    st.subheader("Missed Support Cost Model")
    st.metric("Estimated Cost of Skipped Installs (placeholder)", f"${r['est_cost_total']:,.0f}")
    st.caption("Tiered placeholder assumptions — no real support-case data exists yet to confirm actual call-in rates.")

    st.subheader("Three Estimation Methods for Missed Install Value")
    coef, exponent, r2 = r["power_law"]
    skipped = r["skipped_detail"]
    est_totals = pd.Series({
        "Tier-Based Median": skipped["est_tier"].sum(),
        "Power-Law Model": skipped["est_power_law"].sum(),
        "Flat 15% of ACV": skipped["est_flat_pct"].sum(),
    })
    st.bar_chart(est_totals)
    st.caption(f"Power-law fit: R\u00b2 = {r2:.2f} — directional, not a precise per-deal predictor.")
