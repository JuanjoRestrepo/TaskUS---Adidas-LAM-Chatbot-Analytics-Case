"""
Export processed datasets for Power BI consumption.
Generates three clean Excel files in data/exports/ directory.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(r"C:\Users\restr\Desktop\adidas-chatbot-case")
DATA_PATH   = ROOT / "data" / "raw" / "Business_Case_Chatbot_data_Raw_Data.xlsx"
EXPORT_DIR  = ROOT / "data" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. Load & clean raw sheets ───────────────────────────────────────────────
def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace(r"[^\w]", "", regex=True)
    )
    return df

def build_category_table(df: pd.DataFrame, handling_channel: str) -> pd.DataFrame:
    return (
        df[["contact_reason", "conteo_de_filas", "percentage"]]
        .dropna(subset=["contact_reason"])
        .rename(columns={"conteo_de_filas": "volume"})
        .assign(handling_channel=handling_channel)
        [["handling_channel", "contact_reason", "volume", "percentage"]]
    )

def build_subcategory_table(df: pd.DataFrame, handling_channel: str) -> pd.DataFrame:
    return (
        df[["contact_reason1", "sub_category", "conteo_de_filas1", "percentage1"]]
        .rename(columns={
            "contact_reason1": "contact_reason",
            "conteo_de_filas1": "volume",
            "percentage1": "percentage"
        })
        .assign(handling_channel=handling_channel)
        [["handling_channel", "contact_reason", "sub_category", "volume", "percentage"]]
    )

df_agent  = clean_columns(pd.read_excel(DATA_PATH, sheet_name="Agent handled only volume"))
df_hybrid = clean_columns(pd.read_excel(DATA_PATH, sheet_name="Hybrid Handled only volume"))
df_bot    = clean_columns(pd.read_excel(DATA_PATH, sheet_name="Bot only volume"))

categories_df = pd.concat([
    build_category_table(df_agent,  "Agent Only"),
    build_category_table(df_hybrid, "Hybrid"),
    build_category_table(df_bot,    "Bot Only"),
], ignore_index=True)

subcategories_df = pd.concat([
    build_subcategory_table(df_agent,  "Agent Only"),
    build_subcategory_table(df_hybrid, "Hybrid"),
    build_subcategory_table(df_bot,    "Bot Only"),
], ignore_index=True)

# ── 2. KPI Summary Table ─────────────────────────────────────────────────────
kpi_df = pd.DataFrame({
    "KPI":           ["Containment Rate", "Repeat Rate",  "Resolution Rate"],
    "Current":       [0.48,               0.28,           0.30],
    "Target":        [0.55,               0.18,           0.50],
    "Gap":           [-0.07,              0.10,           -0.20],
    "Direction":     ["Higher is better", "Lower is better", "Higher is better"],
    "Status":        ["Below Target",     "Below Target", "Below Target"],
})

# ── 3. Channel Distribution ──────────────────────────────────────────────────
channel_df = (
    categories_df
    .groupby("handling_channel")["volume"]
    .sum()
    .reset_index()
    .rename(columns={"volume": "total_volume"})
)
channel_df["percentage_of_total"] = channel_df["total_volume"] / channel_df["total_volume"].sum()

# ── 4. Pareto Table ───────────────────────────────────────────────────────────
pareto_df = (
    categories_df
    .groupby("contact_reason")["volume"]
    .sum()
    .reset_index()
    .rename(columns={"volume": "total_volume"})
    .sort_values("total_volume", ascending=False)
    .assign(cumulative_volume=lambda x: x["total_volume"].cumsum())
)
total_vol = pareto_df["total_volume"].sum()
pareto_df["pct_of_total"]    = pareto_df["total_volume"]    / total_vol
pareto_df["cumulative_pct"]  = pareto_df["cumulative_volume"] / total_vol
pareto_df["pareto_rank"]     = range(1, len(pareto_df) + 1)

# ── 5. Pivot: Intent × Channel ───────────────────────────────────────────────
intent_channel_df = (
    categories_df
    .pivot_table(
        index="contact_reason",
        columns="handling_channel",
        values="volume",
        aggfunc="sum",
    )
    .fillna(0)
    .reset_index()
)
intent_channel_df["total_volume"] = intent_channel_df[
    [c for c in intent_channel_df.columns if c != "contact_reason"]
].sum(axis=1)
intent_channel_df = intent_channel_df.sort_values("total_volume", ascending=False)

# ── 6. Automation Opportunity ─────────────────────────────────────────────────
AUTOMATION_INTENTS = {
    "Return status":              {"complexity": "Medium", "integration": "OMS API",         "phase": "30-60 days"},
    "Size":                       {"complexity": "Low",    "integration": "None (FAQ)",       "phase": "0-30 days"},
    "Explain how to order":       {"complexity": "Low",    "integration": "None (FAQ)",       "phase": "0-30 days"},
    "How to return":              {"complexity": "Medium", "integration": "Returns Platform", "phase": "0-30 days"},
    "In transit":                 {"complexity": "Medium", "integration": "Carrier API",      "phase": "30-60 days"},
    "label Request":              {"complexity": "Medium", "integration": "Returns System",   "phase": "30-60 days"},
    "Payment Process Information":{"complexity": "Low",    "integration": "None (FAQ)",       "phase": "0-30 days"},
}
automation_df = (
    subcategories_df[subcategories_df["sub_category"].isin(AUTOMATION_INTENTS.keys())]
    .groupby("sub_category")["volume"]
    .sum()
    .reset_index()
    .rename(columns={"volume": "total_volume"})
    .sort_values("total_volume", ascending=False)
)
meta = pd.DataFrame.from_dict(AUTOMATION_INTENTS, orient="index").reset_index()
meta.columns = ["sub_category", "complexity", "integration_required", "roadmap_phase"]
automation_df = automation_df.merge(meta, on="sub_category", how="left")

# Add bot_only volume and non-bot volume for impact estimation
bot_subcat = (
    subcategories_df[
        (subcategories_df["sub_category"].isin(AUTOMATION_INTENTS.keys())) &
        (subcategories_df["handling_channel"] == "Bot Only")
    ]
    .groupby("sub_category")["volume"].sum()
    .reset_index()
    .rename(columns={"volume": "volume_bot_only"})
)
automation_df = automation_df.merge(bot_subcat, on="sub_category", how="left").fillna(0)
automation_df["volume_non_bot"] = automation_df["total_volume"] - automation_df["volume_bot_only"]
automation_df["automation_potential_60pct"] = (automation_df["volume_non_bot"] * 0.60).round(0).astype(int)

# ── 7. Roadmap Table ──────────────────────────────────────────────────────────
roadmap_df = pd.DataFrame([
    {"phase": "Phase 1: 0-30 Days", "initiative": "Fix Left Blank taxonomy enforcement",
     "category": "Data Governance", "complexity": "Low",
     "kpi_impact": "Resolution Rate +5pp", "volume_impacted": 197506,
     "dependency": "None"},
    {"phase": "Phase 1: 0-30 Days", "initiative": "Activate FAQ: Explain how to order",
     "category": "Support on Ordering", "complexity": "Low",
     "kpi_impact": "Containment Rate +2pp", "volume_impacted": 56523,
     "dependency": "None"},
    {"phase": "Phase 1: 0-30 Days", "initiative": "Fix routing: How to return (flow exists)",
     "category": "Returns & Refunds", "complexity": "Low",
     "kpi_impact": "Containment Rate +1pp", "volume_impacted": 38538,
     "dependency": "Routing rules update"},
    {"phase": "Phase 2: 30-60 Days", "initiative": "OMS Integration: Return status + In transit",
     "category": "Existing Order / Returns", "complexity": "Medium",
     "kpi_impact": "Resolution Rate +8pp, Repeat Rate -4pp", "volume_impacted": 91804,
     "dependency": "OMS API access"},
    {"phase": "Phase 2: 30-60 Days", "initiative": "Returns Platform: label Request automation",
     "category": "Returns & Refunds", "complexity": "Medium",
     "kpi_impact": "Containment Rate +2pp", "volume_impacted": 28405,
     "dependency": "Returns System API"},
    {"phase": "Phase 3: 60-90 Days", "initiative": "NLP retraining: Not defined by Bot",
     "category": "NLP / Taxonomy", "complexity": "Medium",
     "kpi_impact": "False containment elimination", "volume_impacted": 5855,
     "dependency": "NLP platform access"},
    {"phase": "Phase 3: 60-90 Days", "initiative": "AI Agent / LLM fallback for long-tail intents",
     "category": "All Categories", "complexity": "High",
     "kpi_impact": "Resolution Rate +5pp, Repeat Rate -4pp", "volume_impacted": 120000,
     "dependency": "LLM integration, security review"},
])

# ── 8. Undefined Intent Table ─────────────────────────────────────────────────
undefined_df = (
    categories_df[categories_df["contact_reason"] == "Not defined by Bot"]
    [["handling_channel", "volume"]]
    .copy()
)
undefined_df["pct_of_undefined"] = undefined_df["volume"] / undefined_df["volume"].sum()

# ── 9. Left Blank Table ───────────────────────────────────────────────────────
left_blank_df = (
    subcategories_df[subcategories_df["sub_category"] == "Left Blank"]
    .groupby("contact_reason")["volume"]
    .sum()
    .reset_index()
    .rename(columns={"volume": "left_blank_volume"})
    .sort_values("left_blank_volume", ascending=False)
)
cat_totals = categories_df.groupby("contact_reason")["volume"].sum().reset_index().rename(columns={"volume": "category_total"})
left_blank_df = left_blank_df.merge(cat_totals, on="contact_reason", how="left")
left_blank_df["pct_left_blank_within_category"] = left_blank_df["left_blank_volume"] / left_blank_df["category_total"]

# ── 10. Export to Excel (single workbook, multiple sheets) ────────────────────
output_path = EXPORT_DIR / "Adidas_LAM_Chatbot_PowerBI_Data.xlsx"

with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    kpi_df.to_excel(writer,          sheet_name="1_KPI_Summary",          index=False)
    channel_df.to_excel(writer,      sheet_name="2_Channel_Distribution",  index=False)
    pareto_df.to_excel(writer,       sheet_name="3_Pareto_Analysis",       index=False)
    intent_channel_df.to_excel(writer,sheet_name="4_Intent_x_Channel",    index=False)
    automation_df.to_excel(writer,   sheet_name="5_Automation_Opportunity",index=False)
    roadmap_df.to_excel(writer,      sheet_name="6_Roadmap_30_60_90",      index=False)
    undefined_df.to_excel(writer,    sheet_name="7_Undefined_Intent",      index=False)
    left_blank_df.to_excel(writer,   sheet_name="8_Left_Blank_Analysis",   index=False)
    categories_df.to_excel(writer,   sheet_name="9_Categories_Raw",        index=False)
    subcategories_df.to_excel(writer,sheet_name="10_Subcategories_Raw",    index=False)

print(f"[OK] Power BI data exported successfully to:\n   {output_path}")
print(f"\nSheets generated:")
for i, name in enumerate(["1_KPI_Summary", "2_Channel_Distribution", "3_Pareto_Analysis",
                           "4_Intent_x_Channel", "5_Automation_Opportunity", "6_Roadmap_30_60_90",
                           "7_Undefined_Intent", "8_Left_Blank_Analysis",
                           "9_Categories_Raw", "10_Subcategories_Raw"], 1):
    print(f"   {i:02d}. {name}")
