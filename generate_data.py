"""
generate_data.py
Synthetic data generator for the "Solstice Cloud Systems - Aurora" portfolio case study.

Produces three files that mirror the shape and embedded business stories of a real
enterprise install/discount/attach analysis, entirely with fabricated company, SKU,
partner, and seller names:

  1. SKU_Lookup.xlsx           - the product catalog, including a deliberate "trap" SKU
                                  and a retired SKU migrating to a replacement
  2. Aurora_Service_Orders.xlsx - install (Professional Services) and Care (support)
                                  order-level data with Gross/Discount/Net $
  3. Aurora_Commercial_Bookings.xlsx - software + install + care bookings with
                                  Region/Partner/Seller/Term/ACV

Embedded stories (deliberately planted, mirroring a real analysis):
  - A SKU ("AR201#G1") sits in the same Professional Services category as genuine
    install SKUs but is explicitly out of scope per the Lookup table -- a naive
    analyst who trusts the category label alone will overcount attach and
    undercount discount leakage.
  - "AR210" (Quick Deploy) is marked retired after a past date but keeps generating
    orders into recent quarters, with volume rapidly migrating to its replacement
    "AR215" in the most recent quarter.
  - Discount cap policy is 40%; the median deal sits AT the cap, and roughly a third
    of deals exceed it -- concentrated overwhelmingly in Large-tier, 5-year deals.
  - Care (support) discount is bundled with Install discount on the same large,
    multi-year deals -- both get discounted heavily together, not independently.
  - Install value scales with deal size (ACV) but with strong diminishing returns,
    not as a flat percentage -- supporting three different estimation methods for
    "what should missed install have been worth."
  - Attach rate varies sharply by region, with two regions showing near-zero attach.
  - The most recent fiscal quarter (year-end) shows an order-volume surge.
"""

import numpy as np
import pandas as pd
import os

np.random.seed(42)
OUT_DIR = "data"
os.makedirs(OUT_DIR, exist_ok=True)

QUARTERS = ["FY24-Q4", "FY25-Q1", "FY25-Q2", "FY25-Q3"]
QUARTER_WEIGHTS = [0.28, 0.20, 0.24, 0.28]  # year-end surge in Q4, then a dip, recovering

REGIONS = [
    "North America", "EMEA-West", "EMEA-East", "ANZAsia",
    "APAC", "LATAM-North", "LATAM-South", "Japan", "India",
]
# Deliberately give Japan and India near-zero attach, mirroring the real finding
REGION_ATTACH_RATE = {
    "North America": 0.16, "EMEA-West": 0.12, "EMEA-East": 0.09,
    "ANZAsia": 0.18, "APAC": 0.07, "LATAM-North": 0.08,
    "LATAM-South": 0.07, "Japan": 0.01, "India": 0.03,
}
REGION_VOLUME_WEIGHTS = {
    "North America": 0.20, "EMEA-West": 0.14, "EMEA-East": 0.11,
    "ANZAsia": 0.10, "APAC": 0.14, "LATAM-North": 0.11,
    "LATAM-South": 0.08, "Japan": 0.07, "India": 0.05,
}

PARTNERS = [
    "Nova Systems - US", "BluePeak Solutions - DE", "Meridian Tech - JP",
    "Cobalt Integrators - IN", "Halcyon IT - GB", "Vantage Point Corp - US",
    "Ridgeline Networks - CA", "Solace Digital - FR", "Kestrel Consulting - AU",
    "Ironwood Systems - NL", "Silverback Tech - BR", "Orion Cloud Partners - ES",
    "Fathom Solutions - IT", "Cascade Integrations - MX", "Brightline IT - TR",
    "Northfield Technologies - US", "Amberline Systems - SE", "Quaystone - SG",
    "Redwood Partners - CA", "Solvex Consulting - PL", None, None, None,  # some deals have no partner on file
]

FIRST_NAMES = ["Maria", "James", "Wei", "Fatima", "Lucas", "Priya", "Anders", "Sofia",
               "Kenji", "Elena", "Marcus", "Aisha", "Noah", "Yuki", "Diego", "Ingrid",
               "Omar", "Chloe", "Ravi", "Isabel", "Tom", "Nadia", "Felix", "Grace"]
LAST_NAMES = ["Alvarez", "Bergstrom", "Chen", "Dubois", "Eriksson", "Farah", "Gomez",
              "Haddad", "Ivanov", "Jansen", "Kowalski", "Lindqvist", "Mercer", "Nasser",
              "Okafor", "Petrov", "Quintero", "Reyes", "Sato", "Thorne", "Vance", "Weiss"]

def random_seller(n=1, rng=None):
    rng = rng or np.random
    return [f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}" for _ in range(n)]

# ---------------------------------------------------------------------------
# SKU Lookup table -- the catalog, with the deliberate "trap" and "retirement"
# ---------------------------------------------------------------------------
lookup_rows = [
    ("AR201#E1", "Aurora Remote Deploy Essentials", None, "Remote Deploy Essentials"),
    ("AR201#E2", "Aurora Remote Deploy Advanced", None, "Remote Deploy Advanced"),
    ("AR201#N1", "Aurora Remote Deploy Enterprise", None, "Remote Deploy Enterprise"),
    ("AR201#H1", "Aurora Remote HA Deploy Enterprise", None, "Remote HA Deploy Enterprise"),
    ("AR210", "Aurora Quick Deploy", "retired after Nov FY24", "Quick Deploy (legacy)"),
    ("AR215", "Aurora Quick Deploy v2", None, "Quick Deploy v2"),
    ("AR201#G1", "Aurora Professional Services General", "not in scope for Aurora PS attach metric", "Prof Svcs General"),
]
lookup_df = pd.DataFrame(lookup_rows, columns=["KU", "Description", "Note", "Short Name"])

# ---------------------------------------------------------------------------
# Build the SW-eligible opportunity base
# ---------------------------------------------------------------------------
N_OPPS = 1500
region_probs = np.array([REGION_VOLUME_WEIGHTS[r] for r in REGIONS])
region_probs = region_probs / region_probs.sum()

opp_regions = np.random.choice(REGIONS, size=N_OPPS, p=region_probs)
opp_quarters = np.random.choice(QUARTERS, size=N_OPPS, p=QUARTER_WEIGHTS)
opp_terms = np.random.choice([12, 36, 60], size=N_OPPS, p=[0.22, 0.40, 0.38])
opp_rtm = np.random.choice(["Direct", "Indirect"], size=N_OPPS, p=[0.15, 0.85])
opp_partners = [np.random.choice(PARTNERS) if rtm == "Indirect" else None for rtm in opp_rtm]
opp_sellers = random_seller(N_OPPS)

# ACV: log-normal, realistic right-skew
opp_acv = np.round(np.random.lognormal(mean=7.2, sigma=1.3, size=N_OPPS), 2)
opp_acv = np.clip(opp_acv, 80, 250000)
opp_order_value = np.round(opp_acv * (opp_terms / 12), 2)

opp_ids = [f"OPP-{100000+i}" for i in range(N_OPPS)]

bookings_sw_rows = []
for i in range(N_OPPS):
    bookings_sw_rows.append({
        "Opportunity ID": opp_ids[i],
        "Region": opp_regions[i],
        "Partner": opp_partners[i],
        "Seller": opp_sellers[i],
        "Fiscal Quarter": opp_quarters[i],
        "RTM": opp_rtm[i],
        "Order Type": "NewLogo",
        "Terms in Months": opp_terms[i],
        "ACV": opp_acv[i],
        "Financial Order $": opp_order_value[i],
        "L06 BA Name": np.random.choice(
            ["Aurora SW", "Aurora Hypervisor", "Aurora AI", "Aurora Edge"],
            p=[0.55, 0.25, 0.12, 0.08]
        ),
        "Base Product Id": "AR100",
        "Base Product desc": "Aurora Core Platform License",
    })

# ---------------------------------------------------------------------------
# Decide attach (genuine install) and the "trap" SKU, per opportunity
# ---------------------------------------------------------------------------
attach_prob = np.array([REGION_ATTACH_RATE[r] for r in opp_regions])
genuine_attach = np.random.random(N_OPPS) < attach_prob
trap_sku_hit = (np.random.random(N_OPPS) < 0.14) & (~genuine_attach)  # trap mostly hits non-attached opps

def pick_install_sku(quarter):
    """Retired AR210 dominates early quarters; AR215 takes over in the most recent quarter."""
    if quarter == QUARTERS[-1]:
        return np.random.choice(["AR215", "AR201#E1", "AR201#N1", "AR201#H1"], p=[0.55, 0.20, 0.15, 0.10])
    else:
        return np.random.choice(["AR210", "AR201#E1", "AR201#N1", "AR201#H1"], p=[0.55, 0.20, 0.15, 0.10])

service_order_rows = []
order_id_counter = 500000

def make_discount(gross, is_large, is_5yr, base_low=0.22, base_high=0.35):
    """Base discount, with a strong kick for Large + 5yr deals to concentrate cap breaches there."""
    base = np.random.uniform(base_low, base_high)
    if is_large and is_5yr:
        # heavy concentration of extreme discounts here, mirroring the real finding
        kick = np.random.choice([0.15, 0.35, 0.55], p=[0.30, 0.35, 0.35])
        base += kick
        if np.random.random() < 0.28:
            base = np.random.uniform(0.85, 0.99)  # near-total give-away, the extreme tail
    elif is_5yr:
        base += np.random.uniform(0.05, 0.20)
    elif is_large:
        base += np.random.uniform(0.03, 0.12)
    return min(base, 0.99)

LARGE_ACV_THRESHOLD = 1800  # matches roughly the same tier boundary used in the real analysis

for i in range(N_OPPS):
    opp = opp_ids[i]
    quarter = opp_quarters[i]
    acv = opp_acv[i]
    term = opp_terms[i]
    is_large = acv > LARGE_ACV_THRESHOLD
    is_5yr = term == 60

    # Install order (genuine attach)
    if genuine_attach[i]:
        sku = pick_install_sku(quarter)
        # Install gross scales with ACV but with strong diminishing returns (power-law-ish)
        gross = round(280 * (acv ** 0.37) * np.random.uniform(0.8, 1.25), 2)
        discount_pct = make_discount(gross, is_large, is_5yr)
        discount = round(gross * discount_pct, 2)
        net = round(gross - discount, 2)
        order_id_counter += 1
        service_order_rows.append({
            "Opportunity ID": opp, "SKU": sku, "Category": "Aurora Professional Services",
            "Financial Close Fiscal Quarter": quarter,
            "Order Gross $": gross, "Order Discount $": -discount, "Order Net $": net,
        })
        care_discount_pct = discount_pct * np.random.uniform(0.75, 1.05)  # bundled: care echoes install discount
    else:
        care_discount_pct = np.random.uniform(0.20, 0.35)

    # Trap SKU (out-of-scope PS General) -- sits in the same category, should NOT count as install
    if trap_sku_hit[i]:
        gross = round(np.random.uniform(400, 3000), 2)
        discount = round(gross * np.random.uniform(0.20, 0.45), 2)
        net = round(gross - discount, 2)
        order_id_counter += 1
        service_order_rows.append({
            "Opportunity ID": opp, "SKU": "AR201#G1", "Category": "Aurora Professional Services",
            "Financial Close Fiscal Quarter": quarter,
            "Order Gross $": gross, "Order Discount $": -discount, "Order Net $": net,
        })

    # Care (support) order -- near-mandatory attach (~95%)
    if np.random.random() < 0.95:
        care_sku = {12: "CARE1Y", 36: "CARE3Y", 60: "CARE5Y"}[term]
        care_gross = round(acv * np.random.uniform(0.06, 0.11) * (term / 12), 2)
        care_discount = round(care_gross * min(care_discount_pct, 0.97), 2)
        care_net = round(care_gross - care_discount, 2)
        order_id_counter += 1
        service_order_rows.append({
            "Opportunity ID": opp, "SKU": care_sku, "Category": "Aurora Care",
            "Financial Close Fiscal Quarter": quarter,
            "Order Gross $": care_gross, "Order Discount $": -care_discount, "Order Net $": care_net,
        })

bookings_df = pd.DataFrame(bookings_sw_rows)
service_orders_df = pd.DataFrame(service_order_rows)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
lookup_df.to_excel(f"{OUT_DIR}/SKU_Lookup.xlsx", sheet_name="Lookup", index=False)
bookings_df.to_excel(f"{OUT_DIR}/Aurora_Commercial_Bookings.xlsx", sheet_name="Export", index=False)
service_orders_df.to_excel(f"{OUT_DIR}/Aurora_Service_Orders.xlsx", sheet_name="Service Orders", index=False)

print(f"Opportunities: {N_OPPS}")
print(f"Genuine install attach: {genuine_attach.sum()} ({genuine_attach.mean()*100:.1f}%)")
print(f"Trap SKU hits: {trap_sku_hit.sum()}")
print(f"Service order rows: {len(service_orders_df)}")
print("Saved to data/: SKU_Lookup.xlsx, Aurora_Commercial_Bookings.xlsx, Aurora_Service_Orders.xlsx")
