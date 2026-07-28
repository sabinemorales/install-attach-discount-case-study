"""
build_model.py
Builds the full Discount/Attach/Cost live Excel model for the synthetic
Solstice Cloud Systems - Aurora dataset (produced by generate_data.py).

Mirrors the structure of a real enterprise install/discount/attach analysis:
Assumptions, Discount Leakage (cap-breach AND target-average views), Attach
Rate What-If, Missed Support Cost Model, Leakage by SKU, and full raw detail
tabs with three independent estimation methods for missing install value.
"""

import numpy as np
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Styling constants
# ---------------------------------------------------------------------------
BLUE = Font(color="0000FF")
BLUE_BOLD = Font(color="0000FF", bold=True)
BLACK = Font(color="000000")
BLACK_BOLD = Font(color="000000", bold=True)
GREEN = Font(color="008000")
GREEN_BOLD = Font(color="008000", bold=True)
TITLE_FONT = Font(size=14, bold=True, color="1F1F1F")
SUB_FONT = Font(size=10, italic=True, color="595959")
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
KEY_LEVER_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
CALLOUT_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CURRENCY = '$#,##0'
PCT = '0.0%'

def set_col_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

# ===========================================================================
# STEP 1: Load synthetic data and run the analysis in pandas
# ===========================================================================
bookings = pd.read_excel("data/Aurora_Commercial_Bookings.xlsx")
orders = pd.read_excel("data/Aurora_Service_Orders.xlsx")
lookup = pd.read_excel("data/SKU_Lookup.xlsx")

INSTALL_SKUS = ['AR201#E1', 'AR201#E2', 'AR201#N1', 'AR201#H1', 'AR210', 'AR215']
CARE_SKUS = ['CARE1Y', 'CARE3Y', 'CARE5Y']
LAST4 = ["FY24-Q4", "FY25-Q1", "FY25-Q2", "FY25-Q3"]
LARGE_THRESH, MID_THRESH = 1800, 350

install_orders = orders[orders['SKU'].isin(INSTALL_SKUS)].copy()
install_opp_ids = set(install_orders['Opportunity ID'])

# --- Eligible / attached / skipped ---
eligible_opps = bookings['Opportunity ID'].unique()
attached_opps = [o for o in eligible_opps if o in install_opp_ids]
skipped_opps = [o for o in eligible_opps if o not in install_opp_ids]

opp_meta = bookings.drop_duplicates('Opportunity ID').set_index('Opportunity ID')[
    ['Region', 'Partner', 'Seller', 'Terms in Months', 'ACV', 'Financial Order $']
]
opp_meta['term_years'] = (opp_meta['Terms in Months'] / 12).round(1)

def tier(acv):
    if pd.isna(acv): return 'n/a'
    if acv > LARGE_THRESH: return 'Large'
    if acv > MID_THRESH: return 'Mid'
    return 'Small'
opp_meta['tier'] = opp_meta['ACV'].map(tier)

# --- Install deal detail (last 4Q), with region/partner/seller/term/ACV/tier ---
install_agg = install_orders.groupby(['Opportunity ID', 'Financial Close Fiscal Quarter']).agg(
    gross=('Order Gross $', 'sum'), discount=('Order Discount $', 'sum')
).reset_index()
install_agg = install_agg[install_agg['gross'] > 0].copy()
install_agg['discount_actual'] = -install_agg['discount']
install_agg = install_agg[install_agg['Financial Close Fiscal Quarter'].isin(LAST4)]
install_agg = install_agg.join(opp_meta, on='Opportunity ID')
install_agg.columns = ['Opportunity ID', 'Quarter', 'Gross $', 'discount_raw', 'Actual Discount $',
                       'Region', 'Partner', 'Seller', 'Terms in Months', 'ACV', 'Financial Order $',
                       'term_years', 'tier']
install_agg = install_agg.drop(columns=['discount_raw'])

# --- Attached deal detail (net $ + full context) ---
net_by_opp = install_orders.groupby('Opportunity ID')['Order Net $'].sum()
attached_detail = pd.DataFrame({'Opportunity ID': attached_opps})
attached_detail['Net $'] = attached_detail['Opportunity ID'].map(net_by_opp)
attached_detail = attached_detail.join(opp_meta, on='Opportunity ID')
attached_detail = attached_detail.dropna(subset=['Net $'])

# --- Skipped deal detail (full context) ---
skipped_detail = pd.DataFrame({'Opportunity ID': skipped_opps}).join(opp_meta, on='Opportunity ID')

# --- SKU detail (last 4Q) ---
sku_names = dict(zip(lookup['KU'], lookup['Short Name']))
sku_detail = install_orders[install_orders['Financial Close Fiscal Quarter'].isin(LAST4)].groupby(
    ['Opportunity ID', 'SKU', 'Financial Close Fiscal Quarter']
).agg(gross=('Order Gross $', 'sum'), discount=('Order Discount $', 'sum')).reset_index()
sku_detail = sku_detail[sku_detail['gross'] > 0].copy()
sku_detail['discount_actual'] = -sku_detail['discount']
sku_detail['sku_name'] = sku_detail['SKU'].map(sku_names)
sku_detail = sku_detail[['Opportunity ID', 'SKU', 'sku_name', 'Financial Close Fiscal Quarter', 'gross', 'discount_actual']]
sku_detail.columns = ['Opportunity ID', 'SKU Code', 'SKU Name', 'Quarter', 'Gross $', 'Actual Discount $']

# --- Power-law fit for install value vs ACV ---
fit_data = attached_detail[(attached_detail['ACV'] > 0) & (attached_detail['Net $'] > 0)]
x = np.log(fit_data['ACV'])
y = np.log(fit_data['Net $'])
b, a = np.polyfit(x, y, 1)
coef, exponent = np.exp(a), b
y_pred = a + b * x
r2 = 1 - ((y - y_pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()

# --- Tier-based median install value from attached deals ---
tier_medians = attached_detail.groupby('tier')['Net $'].median().to_dict()
tier_counts = attached_detail.groupby('tier')['Net $'].count().to_dict()

print("=== Analysis summary ===")
print(f"Eligible: {len(eligible_opps)}  Attached: {len(attached_opps)}  Skipped: {len(skipped_opps)}")
print(f"Attach rate: {len(attached_opps)/len(eligible_opps)*100:.1f}%")
print(f"Install deal detail rows (last 4Q): {len(install_agg)}")
print(f"Power-law fit: coef={coef:.2f} exponent={exponent:.4f} R2={r2:.3f}")
print(f"Tier medians: {tier_medians}")
print(f"Tier counts: {tier_counts}")

# Save intermediate data for the workbook-building step
install_agg.to_pickle("install_agg.pkl")
attached_detail.to_pickle("attached_detail.pkl")
skipped_detail.to_pickle("skipped_detail.pkl")
sku_detail.to_pickle("sku_detail.pkl")

with open("fit_params.txt", "w") as f:
    f.write(f"{coef}\n{exponent}\n{r2}\n")
    for t in ['Large', 'Mid', 'Small']:
        f.write(f"{t}:{tier_medians.get(t, 0)}:{tier_counts.get(t, 0)}\n")
