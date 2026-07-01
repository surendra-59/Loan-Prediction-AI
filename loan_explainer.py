"""
Loan Explainer Module
=====================
Separates two concerns:
  1. SHAP Explanation  - Why was the loan rejected? (top-N feature impacts)
  2. Counterfactual    - What minimal changes flip the prediction to 'accepted'?

Uses scipy.optimize.differential_evolution (gradient-free global optimizer)
which works reliably with tree-based models like CatBoost.
"""

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

# ─────────────────────────────────────────────────────────────
# CONFIGURATION: Feature metadata & realistic constraints
# ─────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    'Age', 'Income', 'LoanAmount', 'CreditScore', 'MonthsEmployed',
    'NumCreditLines', 'InterestRate', 'LoanTerm', 'DTIRatio',
    'Education_High School', "Education_Master's", 'Education_PhD',
    'EmploymentType_Part-time', 'EmploymentType_Self-employed',
    'EmploymentType_Unemployed', 'MaritalStatus_Married',
    'MaritalStatus_Single', 'HasMortgage_Yes', 'HasDependents_Yes',
    'HasCoSigner_Yes'
]

# Features the applicant can realistically change
ACTIONABLE_FEATURES = ['Income', 'LoanAmount', 'LoanTerm', 'MonthsEmployed', 'DTIRatio']

# Realistic bounds derived from the training data (Loan_default.csv)
FEATURE_BOUNDS = {
    'Age':            (18, 69),
    'Income':         (15000, 150000),
    'LoanAmount':     (1000, 250000),
    'CreditScore':    (300, 850),
    'MonthsEmployed': (0, 120),
    'NumCreditLines': (1, 4),
    'InterestRate':   (2.0, 25.0),
    'LoanTerm':       (12, 60),
    'DTIRatio':       (0.1, 0.9),
}

# Allowed directions of change per actionable feature
# 'increase' = only allow increasing, 'decrease' = only allow decreasing, 'both' = either
CHANGE_DIRECTION = {
    'Income':         'increase',
    'LoanAmount':     'decrease',
    'LoanTerm':       'both',
    'MonthsEmployed': 'increase',
    'DTIRatio':       'decrease',
}


# ─────────────────────────────────────────────────────────────
# PART 1: SHAP EXPLANATION
# ─────────────────────────────────────────────────────────────

def explain_with_shap(model, explainer, user_data_df, top_n=5):
    """
    Returns the top-N features contributing to the model's prediction,
    along with prediction probability and SHAP impact table.

    Parameters
    ----------
    model       : trained CatBoost classifier
    explainer   : shap.TreeExplainer instance
    user_data_df: single-row DataFrame with FEATURE_NAMES columns
    top_n       : number of top features to return

    Returns
    -------
    dict with keys:
      - 'probability'   : float, risk probability (class 1)
      - 'prediction'    : str, 'REJECTED' or 'ACCEPTED'
      - 'base_value'    : float, SHAP expected value
      - 'shap_values'   : np.array, raw SHAP values for this sample
      - 'top_features'  : DataFrame with columns [Feature, Value, SHAP_Impact, Direction]
      - 'all_impacts'   : DataFrame with all features sorted by |impact|
    """
    prob_risk = model.predict_proba(user_data_df)[0][1]
    prediction = 'REJECTED' if prob_risk > 0.5 else 'ACCEPTED'

    shap_values = explainer.shap_values(user_data_df)

    # Handle both CatBoost SHAP output formats:
    # Some versions return a list [class0_shap, class1_shap], others return a 2D array
    if isinstance(shap_values, list):
        # Use class 1 (default/risk) SHAP values
        sv = shap_values[1][0] if len(shap_values) == 2 else shap_values[0]
    else:
        sv = shap_values[0]

    base_value = explainer.expected_value
    if isinstance(base_value, (list, np.ndarray)):
        base_value = base_value[1] if len(base_value) == 2 else base_value[0]

    impacts = pd.DataFrame({
        'Feature':     user_data_df.columns,
        'Value':       user_data_df.values[0],
        'SHAP_Impact': sv,
        'Direction':   ['(+) Risk' if s > 0 else '(-) Risk' for s in sv]
    })
    impacts['Abs_Impact'] = impacts['SHAP_Impact'].abs()
    impacts = impacts.sort_values('Abs_Impact', ascending=False)
    top = impacts.head(top_n).drop(columns='Abs_Impact').reset_index(drop=True)

    return {
        'probability':  prob_risk,
        'prediction':   prediction,
        'base_value':   base_value,
        'shap_values':  sv,
        'top_features': top,
        'all_impacts':  impacts.drop(columns='Abs_Impact').reset_index(drop=True),
    }


# ─────────────────────────────────────────────────────────────
# PART 2: COUNTERFACTUAL GENERATION
# ─────────────────────────────────────────────────────────────

def find_counterfactual(
    model,
    user_data_df,
    actionable_features=None,
    threshold=0.5,
    target_prob=0.40,      # aim below threshold with margin
    max_iter=200,
    balance_weight=200.0,  # penalty weight for unbalanced solutions
    seed=42,
):
    """
    Find minimal changes to actionable features that flip prediction
    from 'rejected' to 'accepted' in ONE step.

    Uses scipy.optimize.differential_evolution - a gradient-free global
    optimizer that works reliably with tree models (piecewise-constant surfaces).

    Parameters
    ----------
    model               : trained classifier with predict_proba
    user_data_df        : single-row DataFrame
    actionable_features : list of feature names the user can change
    threshold           : probability above which loan is rejected
    target_prob         : target probability to aim for (with safety margin)
    max_iter            : max optimizer iterations
    seed                : random seed for reproducibility

    Returns
    -------
    dict with keys:
      - 'success'            : bool
      - 'original_prob'      : float
      - 'counterfactual_prob': float
      - 'original_values'    : dict
      - 'suggested_values'   : dict
      - 'changes'            : DataFrame [Feature, Original, Suggested, Change, Change_%]
      - 'counterfactual_df'  : full modified DataFrame ready for prediction
    """
    if actionable_features is None:
        actionable_features = ACTIONABLE_FEATURES

    original = user_data_df.values[0].copy().astype(float)
    columns = list(user_data_df.columns)

    # Get actionable feature indices
    act_idx = [columns.index(f) for f in actionable_features]

    # Build bounds for the optimizer (only actionable features)
    opt_bounds = []
    for feat in actionable_features:
        idx = columns.index(feat)
        orig_val = original[idx]
        lo, hi = FEATURE_BOUNDS.get(feat, (orig_val * 0.5, orig_val * 2.0))

        # Extend bounds to always include the user's current value
        # (prevents inverted bounds when orig_val is outside FEATURE_BOUNDS)
        lo = min(lo, orig_val)
        hi = max(hi, orig_val * 1.5)  # allow headroom above current value

        direction = CHANGE_DIRECTION.get(feat, 'both')
        if direction == 'increase':
            lo = orig_val        # can only go up from current
        elif direction == 'decrease':
            hi = orig_val        # can only go down from current

        # Safety: ensure lo < hi (add small epsilon if equal)
        if lo >= hi:
            hi = lo + max(abs(lo) * 0.01, 1.0)

        opt_bounds.append((lo, hi))

    # Scale factors for normalizing distances (range of each actionable feature)
    scales = np.array([hi - lo for lo, hi in opt_bounds], dtype=float)
    scales[scales <= 0] = 1.0  # avoid division by zero

    orig_actionable = original[act_idx]

    def objective(x):
        """
        Minimize: normalized L2 distance + balance penalty + flip penalty.
        The balance penalty discourages solutions where a single feature
        carries most of the change, producing 2-3 meaningful recommendations.
        """
        # Reconstruct the full feature vector
        modified = original.copy()
        modified[act_idx] = x
        df = pd.DataFrame([modified], columns=columns)

        prob = model.predict_proba(df)[0][1]

        # Normalized distance: how much did we change?
        prop_changes = np.abs((x - orig_actionable) / scales)
        distance = np.sum(prop_changes ** 2)

        # Balance penalty: penalize concentration of change in one feature
        total_change = prop_changes.sum()
        if total_change > 1e-10:
            concentration = np.max(prop_changes) / total_change
            balance_penalty = balance_weight * concentration ** 2
        else:
            balance_penalty = 0.0

        # Flip penalty: heavily penalize solutions that don't flip the prediction
        if prob >= threshold:
            flip_penalty = 1000.0 * (prob - target_prob + 1.0) ** 2
        else:
            # Slight preference for solutions closer to the target_prob
            flip_penalty = 50.0 * (prob - target_prob) ** 2

        return distance + balance_penalty + flip_penalty

    # Run optimizer
    result = differential_evolution(
        objective,
        bounds=opt_bounds,
        maxiter=max_iter,
        seed=seed,
        tol=1e-6,
        atol=1e-6,
        polish=False,    # Don't polish (gradient-based polish won't help tree models)
        init='sobol',    # Better initial sampling coverage
        mutation=(0.5, 1.5),
        recombination=0.9,
    )

    # Build the counterfactual
    cf_values = original.copy()
    cf_values[act_idx] = result.x
    cf_df = pd.DataFrame([cf_values], columns=columns)
    cf_prob = model.predict_proba(cf_df)[0][1]

    # Build changes summary — filter out trivial (<1% and <$10 absolute) changes
    changes_data = []
    for feat, old_val, new_val in zip(actionable_features, orig_actionable, result.x):
        change = new_val - old_val
        pct = (change / old_val * 100) if old_val != 0 else float('inf')
        # Only report meaningful changes: >1% change AND appropriate absolute change
        if feat in ('Income', 'LoanAmount'):
            abs_threshold = 10.0
        elif feat == 'DTIRatio':
            abs_threshold = 0.01  # 1% absolute ratio change
        else:
            abs_threshold = 0.5
            
        if abs(change) > abs_threshold and abs(pct) > 1.0:
            changes_data.append({
                'Feature':   feat,
                'Original':  round(old_val, 2),
                'Suggested': round(new_val, 2),
                'Change':    round(change, 2),
                'Change_%':  round(pct, 1),
            })

    changes_df = pd.DataFrame(changes_data) if changes_data else pd.DataFrame(
        columns=['Feature', 'Original', 'Suggested', 'Change', 'Change_%']
    )

    return {
        'success':             cf_prob < threshold,
        'original_prob':       model.predict_proba(user_data_df)[0][1],
        'counterfactual_prob': cf_prob,
        'original_values':     {f: original[columns.index(f)] for f in actionable_features},
        'suggested_values':    {f: round(result.x[i], 2) for i, f in enumerate(actionable_features)},
        'changes':             changes_df,
        'counterfactual_df':   cf_df,
    }


# ─────────────────────────────────────────────────────────────
# PART 3: COMBINED ANALYSIS (pretty-printed output)
# ─────────────────────────────────────────────────────────────

def analyze_loan_application(model, explainer, user_data_df, top_n=5, threshold=0.5):
    """
    Full analysis: SHAP explanation + counterfactual (if rejected).
    Prints a clean, formatted report.

    Returns
    -------
    dict with keys 'explanation' and 'counterfactual' (None if accepted)
    """
    # ── Step 1: SHAP Explanation ──
    explanation = explain_with_shap(model, explainer, user_data_df, top_n=top_n)

    print("=" * 65)
    print(f"  LOAN PREDICTION: {explanation['prediction']}")
    print(f"  Risk Probability: {explanation['probability']:.2%}")
    print("=" * 65)
    print()

    print(f"[SHAP] Top {top_n} Features Influencing This Decision:")
    print("-" * 55)
    for _, row in explanation['top_features'].iterrows():
        arrow = "[!!]" if row['SHAP_Impact'] > 0 else "[OK]"
        print(f"  {arrow} {row['Feature']:25s}  Value: {row['Value']:>10.2f}  Impact: {row['SHAP_Impact']:+.4f}")
    print()

    # ── Step 2: Counterfactual (only if rejected) ──
    counterfactual = None
    if explanation['prediction'] == 'REJECTED':
        print("[SEARCH] Generating counterfactual explanation...")
        print("    (Finding minimal changes to flip prediction -> ACCEPTED)\n")

        counterfactual = find_counterfactual(
            model, user_data_df, threshold=threshold
        )

        if counterfactual['success']:
            print("[SUCCESS] COUNTERFACTUAL FOUND -- Prediction flips in ONE step!\n")
            print(f"    Before:  {counterfactual['original_prob']:.2%} (REJECTED)")
           
            print()
            print("[CHANGES] Suggested Changes:")
            print("-" * 65)
            print(f"    {'Feature':20s} {'Original':>12s} {'Suggested':>12s} {'Change':>10s} {'%':>8s}")
            print("    " + "-" * 61)
            for _, row in counterfactual['changes'].iterrows():
                print(f"    {row['Feature']:20s} {row['Original']:12.2f} {row['Suggested']:12.2f} {row['Change']:+10.2f} {row['Change_%']:+7.1f}%")
            print()

            # Verify the counterfactual
            # verify_prob = model.predict_proba(counterfactual['counterfactual_df'])[0][1]
            # print(f"[VERIFY] predict_proba on modified input = {verify_prob:.4f}",
            #       "PASS" if verify_prob < threshold else "FAIL")
        else:
            print("[WARNING] Could not find a feasible counterfactual with actionable features alone.")
            print(f"    Best achieved: {counterfactual['counterfactual_prob']:.2%}")
            print("    Consider adjusting non-actionable features or re-evaluating constraints.")
    else:
        print("[OK] Loan is ACCEPTED -- no counterfactual needed.")
        print("    Strengths contributing to acceptance:")
        top_positive = explanation['all_impacts'][
            explanation['all_impacts']['SHAP_Impact'] < 0  # negative SHAP → reduces risk
        ].head(3)
        for _, row in top_positive.iterrows():
            print(f"    [+] {row['Feature']:25s}  Value: {row['Value']:>10.2f}  Impact: {row['SHAP_Impact']:+.4f}")
    print()
    print("=" * 65)

    return {
        'explanation':    explanation,
        'counterfactual': counterfactual,
    }
