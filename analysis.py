"""
analysis.py
Shared analysis logic for the Aurora Install Attach & Discount Leakage app.
Loads (or self-generates) the synthetic dataset and computes every metric
shown on the dashboard and used by the AI features.
"""

import os
import numpy as np
import pandas as pd

DATA_DIR = "data"
INSTALL_SKUS = ['AR201#E1', 'AR201#E2', 'AR201#N1', 'AR201#H1', 'AR210', 'AR215']
LAST4 = ["FY24-Q4", "FY25-Q1", "FY25-Q2", "FY25-Q3"]
LARGE_THRESH, MID_THRESH = 1800, 350


def ensure_data():
    """Generate the synthetic dataset on first run if it doesn't exist yet."""
    if not os.path.exists(f"{DATA_DIR}/Aurora_Commercial_Bookings.xlsx"):
        import generate_data  # running this module's top-level code creates the data files


def load_data():
    ensure_data()
    bookings = pd.read_excel(f"{DATA_DIR}/Aurora_Commercial_Bookings.xlsx")
    orders = pd.read_excel(f"{DATA_DIR}/Aurora_Service_Orders.xlsx")
    lookup = pd.read_excel(f"{DATA_DIR}/SKU_Lookup.xlsx")
    return bookings, orders, lookup


def tier(acv):
    if pd.isna(acv):
        return "n/a"
    if acv > LARGE_THRESH:
        return "Large"
    if acv > MID_THRESH:
        return "Mid"
    return "Small"


def run_full_analysis():
    bookings, orders, lookup = load_data()

    install_orders = orders[orders["SKU"].isin(INSTALL_SKUS)].copy()
    install_opp_ids = set(install_orders["Opportunity ID"])
    trap_orders = orders[orders["SKU"] == "AR201#G1"].copy()
    naive_install_opp_ids = install_opp_ids | set(trap_orders["Opportunity ID"])

    eligible_opps = bookings["Opportunity ID"].unique()
    attached_opps = [o for o in eligible_opps if o in install_opp_ids]
    skipped_opps = [o for o in eligible_opps if o not in install_opp_ids]

    opp_meta = bookings.drop_duplicates("Opportunity ID").set_index("Opportunity ID")[
        ["Region", "Partner", "Seller", "Terms in Months", "ACV", "Financial Order $"]
    ].copy()
    opp_meta["term_years"] = (opp_meta["Terms in Months"] / 12).round(1)
    opp_meta["tier"] = opp_meta["ACV"].map(tier)

    # --- Attach rate: true vs naive, overall and by region ---
    true_rate = len(attached_opps) / len(eligible_opps)
    naive_rate = len(set(eligible_opps) & naive_install_opp_ids) / len(eligible_opps)

    bookings_u = bookings.drop_duplicates("Opportunity ID").copy()
    bookings_u["attached"] = bookings_u["Opportunity ID"].isin(install_opp_ids)
    region_attach = bookings_u.groupby("Region")["attached"].agg(["mean", "size"]).sort_values("mean")
    region_attach.columns = ["attach_rate", "deals"]

    # --- Install deal detail (last 4Q) ---
    install_agg = install_orders.groupby(["Opportunity ID", "Financial Close Fiscal Quarter"]).agg(
        gross=("Order Gross $", "sum"), discount=("Order Discount $", "sum")
    ).reset_index()
    install_agg = install_agg[install_agg["gross"] > 0].copy()
    install_agg["discount_actual"] = -install_agg["discount"]
    install_agg["discount_pct"] = install_agg["discount_actual"] / install_agg["gross"]
    install_agg = install_agg[install_agg["Financial Close Fiscal Quarter"].isin(LAST4)]
    install_agg = install_agg.join(opp_meta, on="Opportunity ID")
    install_agg["excess_cap"] = (install_agg["discount_actual"] - install_agg["gross"] * 0.40).clip(lower=0)
    install_agg["excess_target"] = (install_agg["discount_actual"] - install_agg["gross"] * 0.15).clip(lower=0)

    leakage_by_q = install_agg.groupby("Financial Close Fiscal Quarter").agg(
        deals=("gross", "size"), gross=("gross", "sum"),
        leakage_cap=("excess_cap", "sum"), leakage_target=("excess_target", "sum"),
    ).reindex(LAST4)

    total_leakage_cap = install_agg["excess_cap"].sum()
    total_leakage_target = install_agg["excess_target"].sum()

    # --- Concentration: extreme discount deals ---
    over80 = install_agg[install_agg["discount_pct"] > 0.80]
    extreme_share_deals = len(over80) / len(install_agg) if len(install_agg) else 0
    extreme_share_leakage = over80["excess_cap"].sum() / total_leakage_cap if total_leakage_cap else 0

    # --- SKU breakdown ---
    sku_names = dict(zip(lookup["KU"], lookup["Short Name"]))
    sku_detail = install_orders[install_orders["Financial Close Fiscal Quarter"].isin(LAST4)].groupby(
        ["SKU", "Financial Close Fiscal Quarter"]
    ).agg(gross=("Order Gross $", "sum"), discount=("Order Discount $", "sum")).reset_index()
    sku_detail["discount_actual"] = -sku_detail["discount"]
    sku_by_sku = sku_detail.groupby("SKU").agg(
        deals=("gross", "size"), gross=("gross", "sum"), discount=("discount_actual", "sum")
    )
    sku_by_sku["avg_discount_pct"] = sku_by_sku["discount"] / sku_by_sku["gross"]
    sku_by_sku["sku_name"] = sku_by_sku.index.map(sku_names)
    sku_by_sku["excess_cap"] = (sku_by_sku["discount"] - sku_by_sku["gross"] * 0.40).clip(lower=0)

    # SKU migration by quarter (legacy vs replacement)
    migration = install_orders[install_orders["SKU"].isin(["AR210", "AR215"])].groupby(
        ["Financial Close Fiscal Quarter", "SKU"]
    ).size().unstack(fill_value=0).reindex(LAST4).fillna(0)

    # --- Attached deal detail + tier medians (for estimation methods) ---
    net_by_opp = install_orders.groupby("Opportunity ID")["Order Net $"].sum()
    attached_detail = pd.DataFrame({"Opportunity ID": attached_opps})
    attached_detail["Net $"] = attached_detail["Opportunity ID"].map(net_by_opp)
    attached_detail = attached_detail.join(opp_meta, on="Opportunity ID").dropna(subset=["Net $"])

    tier_medians = attached_detail.groupby("tier")["Net $"].median().to_dict()

    fit_data = attached_detail[(attached_detail["ACV"] > 0) & (attached_detail["Net $"] > 0)]
    x, y = np.log(fit_data["ACV"]), np.log(fit_data["Net $"])
    b, a = np.polyfit(x, y, 1)
    coef, exponent = np.exp(a), b
    y_pred = a + b * x
    r2 = 1 - ((y - y_pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()

    # --- Skipped deal detail with 3 estimation methods ---
    skipped_detail = pd.DataFrame({"Opportunity ID": skipped_opps}).join(opp_meta, on="Opportunity ID")
    skipped_detail["est_tier"] = skipped_detail["tier"].map(tier_medians).fillna(0)
    skipped_detail["est_power_law"] = coef * (skipped_detail["ACV"].clip(lower=1) ** exponent)
    skipped_detail["est_flat_pct"] = skipped_detail["ACV"] * 0.15

    # --- Missed support cost model (placeholder assumptions) ---
    cost_tiers = {"Large": 1.00, "Mid": 0.50, "Small": 0.00}
    skipped_detail["cost_call_prob"] = skipped_detail["tier"].map(cost_tiers).fillna(0)
    est_cost = (skipped_detail["cost_call_prob"] * 400).sum()  # $400 placeholder cost per call

    return {
        "bookings": bookings, "orders": orders, "lookup": lookup,
        "eligible_count": len(eligible_opps), "attached_count": len(attached_opps), "skipped_count": len(skipped_opps),
        "true_rate": true_rate, "naive_rate": naive_rate,
        "region_attach": region_attach,
        "install_agg": install_agg, "leakage_by_q": leakage_by_q,
        "total_leakage_cap": total_leakage_cap, "total_leakage_target": total_leakage_target,
        "extreme_share_deals": extreme_share_deals, "extreme_share_leakage": extreme_share_leakage,
        "sku_by_sku": sku_by_sku, "migration": migration,
        "attached_detail": attached_detail, "skipped_detail": skipped_detail,
        "tier_medians": tier_medians, "power_law": (coef, exponent, r2),
        "est_cost_total": est_cost,
    }
