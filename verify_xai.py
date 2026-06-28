"""Quick verification that the XAI integration in views.py works."""
import os, sys, django

os.environ['DJANGO_SETTINGS_MODULE'] = 'Loan_prediction_AI.settings'
django.setup()

from app.views import shap_explainer, XAI_AVAILABLE, model

results = []
results.append(f"model loaded: {model is not None}")
results.append(f"XAI_AVAILABLE: {XAI_AVAILABLE}")
results.append(f"shap_explainer: {shap_explainer is not None}")

if model and XAI_AVAILABLE and shap_explainer:
    # Test with the same flow as apply_loan
    from app.ml_utils import prepare_user_input
    from loan_explainer import analyze_loan_application
    from nlp_explainer import generate_full_nlp_report

    test_data = {
        "Age": 30, "Income": 60000, "LoanAmount": 100000,
        "CreditScore": 600, "MonthsEmployed": 36, "NumCreditLines": 2,
        "InterestRate": 10.0, "LoanTerm": 36, "DTIRatio": 0.4,
        "Education": "Bachelor's", "EmploymentType": "Full-time",
        "MaritalStatus": "Single", "HasMortgage": "No",
        "HasDependents": "No", "HasCoSigner": "No",
    }
    
    model_input = prepare_user_input(test_data)
    results.append(f"model_input shape: {model_input.shape}")
    
    xai_result = analyze_loan_application(model, shap_explainer, model_input)
    results.append(f"prediction: {xai_result['explanation']['prediction']}")
    results.append(f"probability: {xai_result['explanation']['probability']:.4f}")
    results.append(f"top_features count: {len(xai_result['explanation']['top_features'])}")
    results.append(f"counterfactual: {xai_result['counterfactual'] is not None}")
    
    results.append("INTEGRATION TEST PASSED")
else:
    results.append("SKIPPED: missing model or XAI components")

# Write results to file
with open("verify_xai_result.txt", "w") as f:
    f.write("\n".join(results))
    
print("\n".join(results))
