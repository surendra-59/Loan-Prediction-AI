"""
NLP Loan Explainer Module
=========================
Generates client-friendly natural language explanations for loan predictions
using the Grok API (xAI). Transforms raw SHAP values and counterfactual data
into clear, professional reports with formatted feature tables.

Features:
  1. Natural Language Explanation  - Plain English summary of why a loan was accepted/rejected
  2. Client-Friendly Feature Table - Formatted breakdown of each feature's role
  3. Risk Profile Summary          - Overall risk assessment with category ratings
  4. Actionable Recommendations    - Specific steps to improve loan eligibility
  5. Financial Health Score        - Composite score derived from key indicators
"""

import json
import requests
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

GROK_API_KEY = ""
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-beta"

# Feature descriptions for client-friendly explanations
FEATURE_DESCRIPTIONS = {
    'Age':                          'Applicant Age',
    'Income':                       'Annual Income ($)',
    'LoanAmount':                   'Requested Loan Amount ($)',
    'CreditScore':                  'Credit Score (300-850)',
    'MonthsEmployed':               'Employment Duration (months)',
    'NumCreditLines':               'Number of Active Credit Lines',
    'InterestRate':                  'Interest Rate (%)',
    'LoanTerm':                     'Loan Term (months)',
    'DTIRatio':                     'Debt-to-Income Ratio',
    'Education_High School':        'Education: High School',
    "Education_Master's":           "Education: Master's Degree",
    'Education_PhD':                'Education: PhD',
    'EmploymentType_Part-time':     'Employment: Part-time',
    'EmploymentType_Self-employed': 'Employment: Self-employed',
    'EmploymentType_Unemployed':    'Employment: Unemployed',
    'MaritalStatus_Married':        'Marital Status: Married',
    'MaritalStatus_Single':         'Marital Status: Single',
    'HasMortgage_Yes':              'Has Existing Mortgage',
    'HasDependents_Yes':            'Has Dependents',
    'HasCoSigner_Yes':              'Has Co-Signer',
}

# Risk thresholds for feature-level assessment
FEATURE_RISK_THRESHOLDS = {
    'CreditScore':    {'good': 700, 'moderate': 600, 'poor': 0},
    'DTIRatio':       {'good': 0.3, 'moderate': 0.5, 'poor': 1.0},
    'Income':         {'good': 80000, 'moderate': 40000, 'poor': 0},
    'MonthsEmployed': {'good': 60, 'moderate': 24, 'poor': 0},
    'LoanAmount':     {'good': 50000, 'moderate': 150000, 'poor': 999999},
    'InterestRate':   {'good': 8, 'moderate': 15, 'poor': 100},
}


# ─────────────────────────────────────────────────────────────
# UTILITY: Financial Health Score
# ─────────────────────────────────────────────────────────────

def compute_financial_health_score(user_data_df):
    """
    Computes a composite financial health score (0-100) from key indicators.
    This gives clients one simple number to understand their financial standing.
    """
    data = user_data_df.iloc[0]
    scores = {}

    # Credit Score contribution (40% weight)
    credit = data.get('CreditScore', 500)
    scores['credit'] = min(max((credit - 300) / (850 - 300) * 100, 0), 100)

    # DTI Ratio contribution (25% weight) — lower is better
    dti = data.get('DTIRatio', 0.5)
    scores['dti'] = min(max((1.0 - dti) / 0.9 * 100, 0), 100)

    # Income-to-Loan ratio (20% weight) — higher is better
    income = data.get('Income', 50000)
    loan = data.get('LoanAmount', 50000)
    ratio = income / max(loan, 1)
    scores['income_loan'] = min(ratio * 50, 100)  # ratio of 2 = 100

    # Employment stability (15% weight)
    months_emp = data.get('MonthsEmployed', 0)
    scores['employment'] = min(months_emp / 120 * 100, 100)

    # Weighted composite
    composite = (
        scores['credit'] * 0.40 +
        scores['dti'] * 0.25 +
        scores['income_loan'] * 0.20 +
        scores['employment'] * 0.15
    )

    grade = (
        'Excellent' if composite >= 80 else
        'Good' if composite >= 65 else
        'Fair' if composite >= 45 else
        'Poor' if composite >= 25 else
        'Very Poor'
    )

    return {
        'score': round(composite, 1),
        'grade': grade,
        'breakdown': {
            'Credit Score':        round(scores['credit'], 1),
            'Debt-to-Income':      round(scores['dti'], 1),
            'Income-to-Loan':      round(scores['income_loan'], 1),
            'Employment Stability': round(scores['employment'], 1),
        }
    }


# ─────────────────────────────────────────────────────────────
# UTILITY: Feature Risk Assessment
# ─────────────────────────────────────────────────────────────

def assess_feature_risk(feature_name, value):
    """
    Returns a risk rating ('Good', 'Moderate', 'Concern') for a feature value.
    """
    thresholds = FEATURE_RISK_THRESHOLDS.get(feature_name)
    if not thresholds:
        return 'N/A'

    # For features where higher is better (Income, CreditScore, MonthsEmployed)
    if feature_name in ('CreditScore', 'Income', 'MonthsEmployed'):
        if value >= thresholds['good']:
            return '✅ Good'
        elif value >= thresholds['moderate']:
            return '⚠️ Moderate'
        else:
            return '🔴 Concern'

    # For features where lower is better (DTIRatio, InterestRate, LoanAmount)
    if feature_name in ('DTIRatio', 'InterestRate', 'LoanAmount'):
        if value <= thresholds['good']:
            return '✅ Good'
        elif value <= thresholds['moderate']:
            return '⚠️ Moderate'
        else:
            return '🔴 Concern'

    return 'N/A'


# ─────────────────────────────────────────────────────────────
# FORMATTED CLIENT TABLES
# ─────────────────────────────────────────────────────────────

def build_client_feature_table(explanation_result):
    """
    Builds a rich, client-friendly feature table from SHAP explanation results.

    Returns a formatted string table and a DataFrame.
    """
    top_features = explanation_result['top_features']

    rows = []
    for _, row in top_features.iterrows():
        feat = row['Feature']
        desc = FEATURE_DESCRIPTIONS.get(feat, feat)
        value = row['Value']
        impact = row['SHAP_Impact']
        direction = row['Direction']
        risk = assess_feature_risk(feat, value)

        # Format value nicely
        if feat in ('Income', 'LoanAmount'):
            val_str = f"${value:,.0f}"
        elif feat == 'DTIRatio':
            val_str = f"{value:.0%}"
        elif feat == 'InterestRate':
            # Handle both decimal (0.12) and percentage (12.0) formats
            display_val = value * 100 if value < 1.0 else value
            val_str = f"{display_val:.1f}%"
        elif feat == 'CreditScore':
            val_str = f"{int(value)}"
        elif feat in ('Age', 'MonthsEmployed', 'LoanTerm', 'NumCreditLines'):
            val_str = f"{int(value)}"
        else:
            val_str = 'Yes' if value == 1 else 'No'

        # Impact interpretation
        if abs(impact) > 0.1:
            strength = 'Strong'
        elif abs(impact) > 0.03:
            strength = 'Moderate'
        else:
            strength = 'Slight'

        influence = f"{strength} {'risk increase' if impact > 0 else 'risk decrease'}"

        rows.append({
            'Feature':       desc,
            'Your Value':    val_str,
            'Risk Rating':   risk,
            'Impact':        f"{impact:+.4f}",
            'Influence':     influence,
        })

    table_df = pd.DataFrame(rows)

    # Build formatted string
    header = f"\n{'─' * 95}\n"
    header += f"  {'Feature':<35s} {'Your Value':>12s} {'Risk Rating':>14s} {'Impact':>10s} {'Influence':<22s}\n"
    header += f"{'─' * 95}\n"

    body = ""
    for r in rows:
        body += f"  {r['Feature']:<35s} {r['Your Value']:>12s} {r['Risk Rating']:>14s} {r['Impact']:>10s} {r['Influence']:<22s}\n"

    footer = f"{'─' * 95}\n"

    return header + body + footer, table_df


def build_counterfactual_table(counterfactual_result):
    """
    Builds a client-friendly table showing suggested changes.
    """
    if not counterfactual_result or not counterfactual_result.get('success'):
        return "", pd.DataFrame()

    changes = counterfactual_result['changes']
    if changes.empty:
        return "  No changes needed.\n", changes

    header = f"\n{'─' * 85}\n"
    header += f"  {'What to Change':<25s} {'Current':>14s} {'Recommended':>14s} {'Change':>12s} {'Effort':>12s}\n"
    header += f"{'─' * 85}\n"

    body = ""
    for _, row in changes.iterrows():
        feat = row['Feature']
        desc = FEATURE_DESCRIPTIONS.get(feat, feat)
        orig = row['Original']
        sugg = row['Suggested']
        chg = row['Change']
        pct = row['Change_%']

        # Format values
        if feat in ('Income', 'LoanAmount'):
            orig_str = f"${orig:,.0f}"
            sugg_str = f"${sugg:,.0f}"
            chg_str = f"${chg:+,.0f}"
        elif feat == 'DTIRatio':
            orig_str = f"{orig:.0%}"
            sugg_str = f"{sugg:.0%}"
            chg_str = f"{chg:+.0%}"
        else:
            orig_str = f"{orig:.1f}"
            sugg_str = f"{sugg:.1f}"
            chg_str = f"{chg:+.1f}"

        # Effort level
        if abs(pct) < 10:
            effort = '🟢 Easy'
        elif abs(pct) < 30:
            effort = '🟡 Moderate'
        else:
            effort = '🔴 Significant'

        body += f"  {desc:<25s} {orig_str:>14s} {sugg_str:>14s} {chg_str:>12s} {effort:>12s}\n"

    footer = f"{'─' * 85}\n"

    return header + body + footer, changes


# ─────────────────────────────────────────────────────────────
# GROK API: Natural Language Generation
# ─────────────────────────────────────────────────────────────

def call_grok_api(prompt, system_prompt=None, max_tokens=2048):
    """
    Calls the Grok (xAI) API for natural language generation.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {
            _API_KEY}",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": GROK_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,  # Controlled creativity for professional tone
    }

    try:
        response = requests.post(GROK_API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            return None # Trigger fallback
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def generate_local_nlp_explanation(explanation_result, counterfactual_result=None, 
                                   user_data_df=None, health_score=None):
    """
    Template-based fallback that generates a high-quality explanation 
    locally if the AI API is unavailable.
    """
    prediction = explanation_result['prediction']
    prob = explanation_result['probability']
    
    lines = []
    
    # Header
    if prediction == 'REJECTED':
        lines.append("Analysis of Your Loan Application Status")
        lines.append("Based on our automated risk assessment, your application currently does not meet the minimum requirements for immediate approval.")
    else:
        lines.append("Congratulations! Your Loan Application is Approved")
        lines.append("Our analysis indicates a strong financial profile that meets our lending criteria.")

    lines.append("")
    
    # Financial Health
    if health_score:
        lines.append("Financial Health Assessment:")
        lines.append(f"Your composite Financial Health Score is {health_score['score']}/100, which ranks as '{health_score['grade']}'.")
        
        lowest_component = min(health_score['breakdown'].items(), key=lambda x: x[1])
        highest_component = max(health_score['breakdown'].items(), key=lambda x: x[1])
        
        lines.append(f"- Your strongest area is {highest_component[0]} ({highest_component[1]:.1f}/100).")
        if lowest_component[1] < 50:
            lines.append(f"- The primary area for improvement is your {lowest_component[0]} ({lowest_component[1]:.1f}/100).")

    lines.append("")
    
    # Key Factors
    lines.append("Detailed Factor Analysis:")
    top_factors = explanation_result['top_features']
    
    for _, row in top_factors.iterrows():
        feat = FEATURE_DESCRIPTIONS.get(row['Feature'], row['Feature'])
        impact = "positively" if row['SHAP_Impact'] < 0 else "negatively"
        risk = assess_feature_risk(row['Feature'], row['Value'])
        
        if row['SHAP_Impact'] > 0.05:
            lines.append(f"- {feat}: This is currently a significant risk factor. Rating: {risk}.")
        elif row['SHAP_Impact'] < -0.05:
            lines.append(f"- {feat}: This is a strong point in your application. Rating: {risk}.")
            
    lines.append("")
    
    # Recommendations
    lines.append("Actionable Steps to Improve Your Eligibility:")
    if counterfactual_result and counterfactual_result.get('success'):
        for _, row in counterfactual_result['changes'].iterrows():
            feat = FEATURE_DESCRIPTIONS.get(row['Feature'], row['Feature'])
            if row['Change'] < 0:
                verb = "Reduce"
                target = abs(row['Change'])
            else:
                verb = "Increase"
                target = row['Suggested']
                
            if feat in ('Annual Income ($)', 'Requested Loan Amount ($)'):
                lines.append(f"- {verb} your {feat} by roughly ${target:,.0f}.")
            elif feat == 'Debt-to-Income Ratio':
                lines.append(f"- Aim for a {feat} of {row['Suggested']:.0%}.")
            else:
                lines.append(f"- {verb} your {feat} to approximately {row['Suggested']:.1f}.")
    else:
        lines.append("- Continue maintaining your current credit score and employment stability.")
        lines.append("- Consider a smaller loan amount or providing a co-signer to reduce overall risk.")

    lines.append("")
    lines.append("We encourage you to review these factors and consider re-applying once the recommended changes are achieved. Our goal is to help you reach a position of financial strength for your loan.")
    
    return "\n".join(lines)


def generate_nlp_explanation(explanation_result, counterfactual_result=None,
                              user_data_df=None, health_score=None):
    """
    Uses Grok API to generate a complete natural language explanation
    of the loan prediction for client consumption.

    Parameters
    ----------
    explanation_result  : dict from explain_with_shap()
    counterfactual_result : dict from find_counterfactual() (optional)
    user_data_df        : original user data DataFrame
    health_score        : dict from compute_financial_health_score()

    Returns
    -------
    str : Natural language explanation
    """
    system_prompt = """You are an expert financial advisor AI assistant. Your job is to explain 
loan prediction decisions to clients in clear, professional, empathetic language. 

Rules:
- Be professional but warm and encouraging
- Use simple language, avoid jargon
- Structure your response with clear sections
- When the loan is rejected, focus on what the client CAN do to improve
- When the loan is accepted, highlight strengths and offer tips to maintain eligibility
- Be specific with numbers and actionable advice
- Do NOT use markdown headers (no # symbols) — use plain text formatting with line breaks
- Use bullet points (•) for lists
- Keep sections separated with blank lines
- Reference actual feature values from the data provided
- Be concise but thorough — aim for 200-350 words"""

    # Build the data summary for the prompt
    prediction = explanation_result['prediction']
    probability = explanation_result['probability']

    top_features_info = []
    for _, row in explanation_result['top_features'].iterrows():
        feat = FEATURE_DESCRIPTIONS.get(row['Feature'], row['Feature'])
        impact_type = "increases risk" if row['SHAP_Impact'] > 0 else "decreases risk"
        top_features_info.append(
            f"- {feat}: value={row['Value']:.2f}, SHAP impact={row['SHAP_Impact']:+.4f} ({impact_type})"
        )

    prompt = f"""Generate a client-friendly explanation for this loan application decision.

DECISION: {prediction}
RISK PROBABILITY: {probability:.2%}
"""

    if health_score:
        prompt += f"""
FINANCIAL HEALTH SCORE: {health_score['score']}/100 (Grade: {health_score['grade']})
Score Breakdown:
  - Credit Score Component: {health_score['breakdown']['Credit Score']}/100
  - Debt-to-Income Component: {health_score['breakdown']['Debt-to-Income']}/100
  - Income-to-Loan Component: {health_score['breakdown']['Income-to-Loan']}/100
  - Employment Stability: {health_score['breakdown']['Employment Stability']}/100
"""

    prompt += f"""
TOP FACTORS INFLUENCING THE DECISION:
{chr(10).join(top_features_info)}
"""

    if user_data_df is not None:
        data = user_data_df.iloc[0]
        prompt += f"""
APPLICANT PROFILE:
  - Age: {data.get('Age', 'N/A')}
  - Annual Income: ${data.get('Income', 0):,.0f}
  - Loan Amount Requested: ${data.get('LoanAmount', 0):,.0f}
  - Credit Score: {data.get('CreditScore', 'N/A')}
  - Months Employed: {data.get('MonthsEmployed', 'N/A')}
  - Debt-to-Income Ratio: {data.get('DTIRatio', 'N/A'):.0%}
  - Interest Rate: {data.get('InterestRate', 'N/A')}%
  - Loan Term: {data.get('LoanTerm', 'N/A')} months
"""

    if counterfactual_result and counterfactual_result.get('success'):
        changes_info = []
        for _, row in counterfactual_result['changes'].iterrows():
            feat = FEATURE_DESCRIPTIONS.get(row['Feature'], row['Feature'])
            changes_info.append(
                f"- Change {feat}: from {row['Original']:.2f} to {row['Suggested']:.2f} "
                f"(change of {row['Change']:+.2f}, i.e. {row['Change_%']:+.1f}%)"
            )
        prompt += f"""
SUGGESTED CHANGES TO GET APPROVED (Counterfactual):
These changes would reduce risk from {counterfactual_result['original_prob']:.2%} to {counterfactual_result['counterfactual_prob']:.2%}:
{chr(10).join(changes_info)}
"""

    prompt += """
Please write a complete explanation covering:
1. A warm opening with the decision summary
2. Why this decision was made (referencing the key factors)
3. The financial health assessment
4. Specific, actionable recommendations
5. An encouraging closing statement"""

    # Try Grok API first
    result = call_grok_api(prompt, system_prompt)
    
    if result and "[API Error]" not in result:
        return result
        
    # Fallback to local high-quality template if API fails (403 or other)
    return generate_local_nlp_explanation(explanation_result, counterfactual_result, 
                                          user_data_df, health_score)


# ─────────────────────────────────────────────────────────────
# MAIN: Full NLP-Enhanced Analysis
# ─────────────────────────────────────────────────────────────

def generate_full_nlp_report(explanation_result, counterfactual_result=None,
                              user_data_df=None):
    """
    Generates a complete, client-ready report combining:
    1. Financial Health Score
    2. Formatted Feature Impact Table
    3. Counterfactual Suggestions Table (if applicable)
    4. AI-Generated Natural Language Explanation (via Grok)

    Parameters
    ----------
    explanation_result    : dict from explain_with_shap()
    counterfactual_result : dict from find_counterfactual() (optional)
    user_data_df          : single-row DataFrame with applicant data

    Returns
    -------
    dict with keys:
      - 'health_score'    : financial health score dict
      - 'feature_table'   : formatted feature table string
      - 'cf_table'        : formatted counterfactual table string
      - 'nlp_explanation' : AI-generated natural language explanation
      - 'full_report'     : complete formatted report string
    """
    prediction = explanation_result['prediction']
    probability = explanation_result['probability']

    # ── 1. Financial Health Score ──
    health_score = None
    if user_data_df is not None:
        health_score = compute_financial_health_score(user_data_df)

    # ── 2. Feature Impact Table ──
    feature_table_str, feature_table_df = build_client_feature_table(explanation_result)

    # ── 3. Counterfactual Table ──
    cf_table_str, cf_table_df = build_counterfactual_table(counterfactual_result)

    # ── 4. AI-Generated NLP Explanation ──
    print("\n  ⏳ Generating AI-powered explanation via Grok API...")
    nlp_explanation = generate_nlp_explanation(
        explanation_result, counterfactual_result,
        user_data_df, health_score
    )

    # ── 5. Assemble Full Report ──
    report = []
    report.append("")
    report.append("╔" + "═" * 93 + "╗")
    report.append("║" + "  📋 CLIENT LOAN APPLICATION REPORT".ljust(93) + "║")
    report.append("╚" + "═" * 93 + "╝")
    report.append("")

    # Decision Banner
    if prediction == 'REJECTED':
        emoji = "❌"
        status = "APPLICATION NOT APPROVED"
    else:
        emoji = "✅"
        status = "APPLICATION APPROVED"

    report.append(f"  📊 Decision: {status}")
    report.append(f"  🔍 Risk Probability: {probability:.1%}")
    report.append("")

    # Financial Health Score
    if health_score:
        bar_filled = int(health_score['score'] / 100 * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        report.append(f"  💰 FINANCIAL HEALTH SCORE: {health_score['score']}/100 — {health_score['grade']}")
        report.append(f"     [{bar}]")
        report.append("")
        report.append("     Breakdown:")
        for component, score in health_score['breakdown'].items():
            mini_bar = "█" * int(score / 100 * 10) + "░" * (10 - int(score / 100 * 10))
            report.append(f"       • {component:<25s} {score:>5.1f}/100  [{mini_bar}]")
        report.append("")

    # Feature Impact Table
    report.append("  📌 KEY FACTORS IN THIS DECISION:")
    report.append(feature_table_str)

    # Counterfactual (if applicable)
    if counterfactual_result and counterfactual_result.get('success'):
        report.append("  🔄 RECOMMENDED CHANGES TO IMPROVE ELIGIBILITY:")
        report.append(f"     (These changes could reduce your risk from "
                      f"{counterfactual_result['original_prob']:.1%} → "
                      f"{counterfactual_result['counterfactual_prob']:.1%})")
        report.append(cf_table_str)

    # NLP Explanation
    report.append("  🤖 AI ADVISOR'S ANALYSIS:")
    report.append("  " + "─" * 91)
    for line in nlp_explanation.split('\n'):
        report.append(f"  {line}")
    report.append("  " + "-" * 91)
    report.append("")

    # Footer
    report.append("  " + "─" * 91)
    report.append("  ℹ️  This report is generated by AI and should be used as guidance only.")
    report.append("  📅  Report generated for internal review and client communication.")
    report.append("  " + "-" * 91)
    report.append("")

    full_report = "\n".join(report)

    return {
        'health_score':    health_score,
        'feature_table':   feature_table_str,
        'feature_table_df': feature_table_df,
        'cf_table':        cf_table_str,
        'nlp_explanation': nlp_explanation,
        'full_report':     full_report,
    }
