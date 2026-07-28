"""
ai_engine.py
Handles all communication with the Anthropic API (Claude) for the Aurora
Install Attach & Discount Leakage app.
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _summarize(r):
    """Builds the shared data summary passed into every prompt below."""
    region_lines = r["region_attach"].to_string()
    leakage_lines = r["leakage_by_q"].to_string()
    sku_lines = r["sku_by_sku"][["deals", "gross", "avg_discount_pct", "excess_cap"]].to_string()

    return f"""
ATTACH RATE:
- True attach rate (correct, out-of-scope SKU excluded): {r['true_rate']*100:.1f}%
- Naive attach rate (if the out-of-scope SKU were mistakenly included): {r['naive_rate']*100:.1f}%
- Eligible opportunities: {r['eligible_count']}, Attached: {r['attached_count']}, Skipped: {r['skipped_count']}

ATTACH RATE BY REGION:
{region_lines}

DISCOUNT LEAKAGE BY QUARTER (last 4 quarters):
{leakage_lines}
Total leakage vs 40% cap: ${r['total_leakage_cap']:,.0f}
Total leakage vs 15% target average: ${r['total_leakage_target']:,.0f}

CONCENTRATION: {r['extreme_share_deals']*100:.1f}% of install deals exceed 80% discount, accounting for {r['extreme_share_leakage']*100:.1f}% of total leakage. All such deals are 5-year, Large-tier.

LEAKAGE BY SKU (AR210 is a legacy SKU being retired and replaced by AR215):
{sku_lines}

ESTIMATED COST OF SKIPPED INSTALLS (placeholder support call-in model): ${r['est_cost_total']:,.0f}
"""


def generate_executive_briefing(r):
    prompt = f"""You are an experienced Chief of Staff preparing a briefing for a CEO on install attach and discount performance.

{_summarize(r)}

Write a concise executive briefing (under 250 words) covering:
1. What happened - the 2-3 most important findings
2. Why it matters - the business implication of each
3. What to focus on today - a short, prioritized list

Write in plain, direct, confident language. No fluff, no generic statements."""
    response = client.messages.create(model="claude-sonnet-4-5", max_tokens=800, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


def generate_key_findings(r):
    prompt = f"""You are a sharp business analyst investigating root causes for a CEO.

{_summarize(r)}

Identify the SINGLE most significant risk or anomaly in this data. Then write an analysis (under 300 words) that:
1. Names it precisely
2. Traces likely causes by connecting signals across the data (region, SKU, deal size, term length)
3. States your confidence level (high/medium/low) and why
4. Notes what additional data would confirm or rule out your theory

Write like an analyst genuinely investigating, not just describing numbers."""
    response = client.messages.create(model="claude-sonnet-4-5", max_tokens=700, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


def generate_recommended_actions(r):
    prompt = f"""You are a decisive Chief of Staff giving a CEO a prioritized action list for this week.

{_summarize(r)}

Give exactly 3 recommended actions, ranked by priority. For each:
- The specific action (concrete, not generic advice)
- Which team owns it
- What happens if it's NOT done

Keep the whole response under 200 words. Be direct, not diplomatic."""
    response = client.messages.create(model="claude-sonnet-4-5", max_tokens=500, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


def chat_with_data(r, chat_history, user_question):
    system_prompt = f"""You are a helpful business analyst assistant with access to this install attach and discount leakage dataset.

{_summarize(r)}

Answer the user's questions using only this data. If they ask about something not present here, say clearly that it isn't available, rather than guessing. Be direct and concise."""
    messages = chat_history + [{"role": "user", "content": user_question}]
    response = client.messages.create(model="claude-sonnet-4-5", max_tokens=600, system=system_prompt, messages=messages)
    return response.content[0].text
