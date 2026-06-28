"""Quick validation: load model, run SHAP + counterfactual + NLP explanation, verify prediction flips."""
import pickle
import pandas as pd
import shap
from loan_explainer import FEATURE_NAMES, analyze_loan_application
from nlp_explainer import generate_full_nlp_report

# Load model
with open('cat_model.pkl', 'rb') as f:
    model = pickle.load(f)

explainer = shap.TreeExplainer(model)

# # Test Case: High-risk applicant
high_risk_user = pd.DataFrame([[
    21, #Age
    30000, #Income
    50000, #LoanAmount
    400, #CreditSc
    20, #MonthEmployed
    5, #NumCreditLines
    0.12, #InterestRate
    70, #LoanTerm
    0.60, #DTIRatio

    1, 0, 0, #Education_High School, Education_Master's, Education_PhD
    0, 0, 1, #EmploymentType_Part-time, EmploymentType_Self-employed, EmploymentType_Unemployed
    0, 1, #MaritalStatus_Married, MaritalStatus_Single
    0, #HasMortgage_Yes
    1, #HasDependents_Yes
    0 #HasCoSigner_Yes
]
], columns=FEATURE_NAMES)


# ── Step 1: Run the original SHAP + counterfactual analysis ──
result = analyze_loan_application(model, explainer, high_risk_user)

# ── Step 2: Generate NLP-enhanced client report ──
print("\n" + "=" * 65)
print("  GENERATING CLIENT-FRIENDLY NLP REPORT...")
print("=" * 65)

nlp_report = generate_full_nlp_report(
    explanation_result=result['explanation'],
    counterfactual_result=result['counterfactual'],
    user_data_df=high_risk_user,
)

# Print the full report
print(nlp_report['full_report'])


###### Range of values for each feature #######
    # 'Age':            (18, 69),
    # 'Income':         (15000, 150000),
    # 'LoanAmount':     (1000, 250000),
    # 'CreditScore':    (300, 850),
    # 'MonthsEmployed': (0, 120),
    # 'NumCreditLines': (1, 4),
    # 'InterestRate':   (2.0, 25.0),
    # 'LoanTerm':       (12, 60),
    # 'DTIRatio':       (0.1, 0.9),

# Also test with a low-risk user
# low_risk_user = pd.DataFrame([[
#     45, 120000, 20000, 800, 120, 2, 0.04, 36, 0.2,
#     0, 1, 0, 0, 0, 0, 1, 0, 1, 1, 1
# ]], columns=FEATURE_NAMES)


# result2 = analyze_loan_application(model, explainer, low_risk_user)
# nlp_report2 = generate_full_nlp_report(
#     explanation_result=result2['explanation'],
#     counterfactual_result=result2['counterfactual'],
#     user_data_df=low_risk_user,
# )
# print(nlp_report2['full_report'])
