from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .models import CustomUser, KYC, LoanApplication
from .decorators import role_required
from .ml_utils import prepare_user_input
import joblib
from concurrent.futures import ThreadPoolExecutor

# Explainable AI imports
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import shap
    from loan_explainer import analyze_loan_application, FEATURE_NAMES
    from nlp_explainer import generate_full_nlp_report, FEATURE_DESCRIPTIONS, assess_feature_risk
    XAI_AVAILABLE = True
except ImportError as e:
    XAI_AVAILABLE = False
    print(f"WARNING: Explainable AI modules not available: {e}")

# Load ML model once
try:
    model = joblib.load("cat_model.pkl")
except:
    model = None
    print("WARNING: ML model not loaded. Prediction functionality will be disabled.")

# Initialize SHAP explainer (once at startup)
shap_explainer = None
if model and XAI_AVAILABLE:
    try:
        shap_explainer = shap.TreeExplainer(model)
        print("SHAP TreeExplainer initialized successfully.")
    except Exception as e:
        print(f"WARNING: Could not initialize SHAP explainer: {e}")

# -------------------------------
# Home View
# -------------------------------
def home(request):
    if request.user.is_authenticated:
        if request.user.user_type == "BANKER":
            return redirect("banker_dashboard")
        else:
            return redirect("user_dashboard")
    return redirect("login")


# -------------------------------
# Register View
# -------------------------------
def register_view(request):
    if request.user.is_authenticated:
        if request.user.user_type == "BANKER":
            return redirect("banker_dashboard")
        else:
            return redirect("user_dashboard")

    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        terms = request.POST.get("terms")

        if not terms:
            messages.error(request, "You must accept Terms & Conditions.")
            return redirect("register")
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("register")
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "Phone number already exists.")
            return redirect("register")

        CustomUser.objects.create_user(
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            password=password,
            user_type="USER"
        )

        messages.success(request, "Account created successfully. Please login.")
        return redirect("login")

    return render(request, "register.html")


# -------------------------------
# Login View
# -------------------------------
def login_view(request):
    if request.user.is_authenticated:
        if request.user.user_type == "BANKER":
            return redirect("banker_dashboard")
        else:
            return redirect("user_dashboard")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)
            return redirect("banker_dashboard" if user.user_type == "BANKER" else "user_dashboard")
        else:
            messages.error(request, "Invalid email or password.")
            return redirect("login")

    return render(request, "login.html")


# -------------------------------
# Logout View
# -------------------------------
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("login")


# -------------------------------
# User Dashboard
# -------------------------------
@login_required
@role_required(allowed_roles=["USER"])
def user_dashboard(request):
    kyc = KYC.objects.filter(user=request.user).first()
    loans = LoanApplication.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "User/user_dashboard.html", {"kyc": kyc, "loans": loans})


# -------------------------------
# Banker Dashboard
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def banker_dashboard(request):
    total_kyc = KYC.objects.count()
    pending_kyc = KYC.objects.filter(status="Pending").count()
    approved_kyc = KYC.objects.filter(status="Approved").count()
    rejected_kyc = KYC.objects.filter(status="Rejected").count()
    
    total_loans = LoanApplication.objects.count()
    pending_loans = LoanApplication.objects.filter(status="PENDING").count()
    approved_loans = LoanApplication.objects.filter(status="APPROVED").count()
    rejected_loans = LoanApplication.objects.filter(status="REJECTED").count()

    kyc_list = KYC.objects.all().order_by('-id')[:10]  # Last 10 KYC
    loan_list = LoanApplication.objects.all().order_by('-created_at')[:10]  # Last 10 Loans

    context = {
        "kyc_list": kyc_list,
        "loan_list": loan_list,
        "total_kyc": total_kyc,
        "pending_kyc": pending_kyc,
        "approved_kyc": approved_kyc,
        "rejected_kyc": rejected_kyc,
        "total_loans": total_loans,
        "pending_loans": pending_loans,
        "approved_loans": approved_loans,
        "rejected_loans": rejected_loans,
    }

    return render(request, "Banker/banker_dashboard.html", context)


# -------------------------------
# KYC Form (User)
# -------------------------------
@login_required
@role_required(allowed_roles=["USER"])
def kyc_form(request):
    kyc = KYC.objects.filter(user=request.user).first()

    if kyc and kyc.status == "Approved":
        messages.error(request, "KYC already approved. Editing not allowed.")
        return redirect("user_dashboard")

    user = request.user

    if request.method == "POST":
        photo = request.FILES.get("photograph")
        if photo and photo.size > 2 * 1024 * 1024:
            messages.error(request, "Image too large (max 2MB).")
            return redirect("kyc_form")

        if kyc:
            # Update existing KYC
            kyc.date_of_birth = request.POST.get("date_of_birth")
            kyc.gender = request.POST.get("gender")
            kyc.father_spouse_name = request.POST.get("father_spouse_name")
            kyc.marital_status = request.POST.get("marital_status")
            kyc.current_address = request.POST.get("current_address")
            kyc.permanent_address = request.POST.get("permanent_address")
            kyc.occupation_type = request.POST.get("occupation_type")
            kyc.annual_income = request.POST.get("annual_income")
            kyc.source_of_funds = request.POST.get("source_of_funds")
            kyc.nature_of_business = request.POST.get("nature_of_business")
            kyc.purpose_of_account = request.POST.get("purpose_of_account")

            if request.FILES.get("id_proof"):
                kyc.id_proof = request.FILES.get("id_proof")
            if photo:
                kyc.photograph = photo

            if kyc.status == "Rejected":
                kyc.status = "Pending"

            kyc.save()
            messages.success(request, "KYC Updated Successfully.")

        else:
            # Create new KYC
            KYC.objects.create(
                user=user,
                full_name=user.full_name,
                mobile_number=user.phone_number,
                email=user.email,
                date_of_birth=request.POST.get("date_of_birth"),
                gender=request.POST.get("gender"),
                father_spouse_name=request.POST.get("father_spouse_name"),
                marital_status=request.POST.get("marital_status"),
                current_address=request.POST.get("current_address"),
                permanent_address=request.POST.get("permanent_address"),
                occupation_type=request.POST.get("occupation_type"),
                annual_income=request.POST.get("annual_income"),
                source_of_funds=request.POST.get("source_of_funds"),
                nature_of_business=request.POST.get("nature_of_business"),
                purpose_of_account=request.POST.get("purpose_of_account"),
                id_proof=request.FILES.get("id_proof"),
                photograph=photo,
            )
            messages.success(request, "KYC Submitted Successfully.")

        return redirect("user_dashboard")

    context = {
        "kyc": kyc,
        "user_data": {
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
        },
    }
    return render(request, "kyc_form.html", context)


# -------------------------------
# Update KYC Status (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def update_kyc_status(request, kyc_id, action):
    kyc = get_object_or_404(KYC, id=kyc_id)

    if action == "approve":
        kyc.status = "Approved"
        messages.success(request, "KYC Approved")

        user = kyc.user
        if user:
            if kyc.full_name and user.full_name != kyc.full_name:
                user.full_name = kyc.full_name
            if kyc.email and user.email != kyc.email:
                user.email = kyc.email
            if kyc.mobile_number and user.phone_number != kyc.mobile_number:
                user.phone_number = kyc.mobile_number
            user.save()

    elif action == "reject":
        kyc.status = "Rejected"
        messages.error(request, "KYC Rejected")
    else:
        messages.error(request, "Invalid action")

    kyc.save()
    return redirect("kyc_applications")


# -------------------------------
# View Single KYC (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def view_kyc(request, kyc_id):
    kyc = get_object_or_404(KYC, id=kyc_id)
    return render(request, "Banker/view_kyc.html", {"kyc": kyc})


# -------------------------------
# KYC Applications List (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def kyc_applications(request):
    print("="*50)
    print("KYC APPLICATIONS VIEW IS BEING CALLED")
    print(f"User: {request.user.email}")
    print(f"User Type: {request.user.user_type}")
    print("="*50)
    
    # Check if KYC table has data
    kyc_count = KYC.objects.count()
    print(f"Total KYC records in database: {kyc_count}")
    
    # Get all KYC records
    kyc_list = KYC.objects.all().order_by("-id")
    
    # Print each record
    for kyc in kyc_list:
        print(f"KYC ID: {kyc.id}, User: {kyc.user.full_name if kyc.user else 'No User'}, Status: {kyc.status}")
    
    context = {
        "kyc_list": kyc_list,
    }
    
    print("Rendering template: Banker/kyc_applications.html")
    return render(request, "Banker/kyc_applications.html", context)


# -------------------------------
# Apply for Loan (User) - COMBINED VERSION
# -------------------------------
@login_required
@role_required(allowed_roles=["USER"])
def apply_loan(request):
    prediction = None
    probability = None
    xai_context = {}  # Explainable AI results
    
    # Check KYC verification
    kyc = KYC.objects.filter(user=request.user).first()
    if not kyc:
        messages.error(request, "Please complete KYC before applying for a loan.")
        return redirect("kyc_form")
    
    if kyc.status != "Approved":
        messages.error(request, "Your KYC must be verified before applying for a loan.")
        return redirect("user_dashboard")
    
    # Check active loan
    active_loan = LoanApplication.objects.filter(
        user=request.user,
        status="APPROVED"
    ).exists()
    
    if active_loan:
        messages.error(request, "Please clear your previous loan before applying for a new one.")
        return redirect("user_dashboard")
    
    if request.method == "POST":
        
        try:
            # Collect form data
            user_data = {
                "Age": int(request.POST.get("Age")),
                "Income": float(request.POST.get("Income")),
                "LoanAmount": float(request.POST.get("LoanAmount")),
                "CreditScore": int(request.POST.get("CreditScore")),
                "MonthsEmployed": int(request.POST.get("MonthsEmployed")),
                "NumCreditLines": int(request.POST.get("NumCreditLines")),
                "InterestRate": float(request.POST.get("InterestRate")),
                "LoanTerm": int(request.POST.get("LoanTerm")),
                "DTIRatio": float(request.POST.get("DTIRatio")),
                "Education": request.POST.get("Education"),
                "EmploymentType": request.POST.get("EmploymentType"),
                "MaritalStatus": request.POST.get("MaritalStatus"),
                "HasMortgage": request.POST.get("HasMortgage"),
                "HasDependents": request.POST.get("HasDependents"),
                "HasCoSigner": request.POST.get("HasCoSigner"),
            }
            
            # ML Prediction (if model is loaded)
            model_input = None
            if model:
                try:
                    model_input = prepare_user_input(user_data)
                    result = model.predict(model_input)[0]
                    probability = model.predict_proba(model_input)[0][1]
                    prediction = "High Risk" if result == 1 else "Low Risk"
                except Exception as e:
                    messages.error(request, f"Error in prediction: {str(e)}")
                    prediction = "Pending"
                    probability = 0.0
            else:
                prediction = "Pending"
                probability = 0.0
                messages.warning(request, "ML model not available. Application submitted for manual review.")
            
            # ── Explainable AI Analysis ──
            if model and model_input is not None and shap_explainer and XAI_AVAILABLE:
                try:
                    # Run SHAP + counterfactual analysis
                    xai_result = analyze_loan_application(model, shap_explainer, model_input)

                    # Run NLP report and DB save in parallel
                    def _generate_nlp():
                        return generate_full_nlp_report(
                            explanation_result=xai_result['explanation'],
                            counterfactual_result=xai_result['counterfactual'],
                            user_data_df=model_input,
                        )

                    def _save_loan():
                        return LoanApplication.objects.create(
                            user=request.user,
                            age=user_data["Age"],
                            income=user_data["Income"],
                            loan_amount=user_data["LoanAmount"],
                            credit_score=user_data["CreditScore"],
                            months_employed=user_data["MonthsEmployed"],
                            num_credit_lines=user_data["NumCreditLines"],
                            interest_rate=user_data["InterestRate"],
                            loan_term=user_data["LoanTerm"],
                            dti_ratio=user_data["DTIRatio"],
                            education=user_data["Education"],
                            employment_type=user_data["EmploymentType"],
                            marital_status=user_data["MaritalStatus"],
                            has_mortgage=user_data["HasMortgage"],
                            has_dependents=user_data["HasDependents"],
                            has_cosigner=user_data["HasCoSigner"],
                            prediction_result=prediction,
                            prediction_probability=probability,
                        )

                    with ThreadPoolExecutor(max_workers=2) as executor:
                        nlp_future = executor.submit(_generate_nlp)
                        db_future = executor.submit(_save_loan)
                        nlp_report = nlp_future.result()
                        loan = db_future.result()
                    
                    # Build feature impacts for template
                    feature_impacts = []
                    for _, row in xai_result['explanation']['top_features'].iterrows():
                        feat_name = row['Feature']
                        desc = FEATURE_DESCRIPTIONS.get(feat_name, feat_name)
                        value = row['Value']
                        impact = row['SHAP_Impact']
                        risk = assess_feature_risk(feat_name, value)
                        
                        # Format value for display
                        if feat_name in ('Income', 'LoanAmount'):
                            val_str = f"${value:,.0f}"
                        elif feat_name == 'DTIRatio':
                            val_str = f"{value:.0%}"
                        elif feat_name == 'InterestRate':
                            display_val = value * 100 if value < 1.0 else value
                            val_str = f"{display_val:.1f}%"
                        elif feat_name in ('CreditScore', 'Age', 'MonthsEmployed', 'LoanTerm', 'NumCreditLines'):
                            val_str = f"{int(value)}"
                        else:
                            val_str = 'Yes' if value == 1 else 'No'
                        
                        # Impact strength
                        if abs(impact) > 0.1:
                            strength = 'Strong'
                        elif abs(impact) > 0.03:
                            strength = 'Moderate'
                        else:
                            strength = 'Slight'
                        influence = f"{strength} {'risk increase' if impact > 0 else 'risk decrease'}"
                        
                        feature_impacts.append({
                            'feature': desc,
                            'value': val_str,
                            'risk': risk,
                            'impact': f"{impact:+.4f}",
                            'influence': influence,
                            'is_risk': impact > 0,
                        })
                    
                    # Build counterfactual changes for template
                    cf_changes = []
                    cf_result = xai_result.get('counterfactual')
                    if cf_result and cf_result.get('success'):
                        for _, row in cf_result['changes'].iterrows():
                            feat = row['Feature']
                            desc = FEATURE_DESCRIPTIONS.get(feat, feat)
                            orig = row['Original']
                            sugg = row['Suggested']
                            chg = row['Change']
                            pct = row['Change_%']
                            
                            if feat in ('Income', 'LoanAmount'):
                                orig_str = f"${orig:,.0f}"
                                sugg_str = f"${sugg:,.0f}"
                                chg_str = f"${chg:+,.0f}"
                            elif feat == 'DTIRatio':
                                orig_str = f"{orig:.0%}"
                                sugg_str = f"{sugg:.0%}"
                                chg_str = f"{chg:+.0%}"
                            else:
                                orig_str = f"{orig:.0f}"
                                sugg_str = f"{sugg:.0f}"
                                chg_str = f"{chg:+.0f}"
                            
                            if abs(pct) < 10:
                                effort = 'Easy'
                                effort_class = 'easy'
                            elif abs(pct) < 30:
                                effort = 'Moderate'
                                effort_class = 'moderate'
                            else:
                                effort = 'Significant'
                                effort_class = 'significant'
                            
                            cf_changes.append({
                                'feature': desc,
                                'original': orig_str,
                                'suggested': sugg_str,
                                'change': chg_str,
                                'change_pct': f"{pct:+.1f}%",
                                'effort': effort,
                                'effort_class': effort_class,
                            })
                    
                    # Build health score breakdown for template
                    health_breakdown = []
                    if nlp_report.get('health_score'):
                        hs = nlp_report['health_score']
                        for component, score in hs['breakdown'].items():
                            health_breakdown.append({
                                'component': component,
                                'score': round(score, 1),
                                'bar_width': int(score),
                            })
                    
                    xai_context = {
                        'health_score': nlp_report.get('health_score'),
                        'health_breakdown': health_breakdown,
                        'feature_impacts': feature_impacts,
                        'cf_changes': cf_changes,
                        'cf_original_prob': f"{cf_result['original_prob']:.1%}" if cf_result and cf_result.get('success') else None,
                        'cf_new_prob': f"{cf_result['counterfactual_prob']:.1%}" if cf_result and cf_result.get('success') else None,
                        'nlp_explanation': nlp_report.get('nlp_explanation', ''),
                        'xai_available': True,
                    }
                    
                    # DB save already done above in parallel
                    db_saved = True
                    
                except Exception as e:
                    print(f"XAI Error: {e}")
                    import traceback
                    traceback.print_exc()
                    xai_context = {'xai_available': False, 'xai_error': str(e)}
                    db_saved = False
            else:
                db_saved = False
            
            # Save to database (only if not already saved in parallel above)
            if not db_saved:
                loan = LoanApplication.objects.create(
                    user=request.user,
                    age=user_data["Age"],
                    income=user_data["Income"],
                    loan_amount=user_data["LoanAmount"],
                    credit_score=user_data["CreditScore"],
                    months_employed=user_data["MonthsEmployed"],
                    num_credit_lines=user_data["NumCreditLines"],
                    interest_rate=user_data["InterestRate"],
                    loan_term=user_data["LoanTerm"],
                    dti_ratio=user_data["DTIRatio"],
                    education=user_data["Education"],
                    employment_type=user_data["EmploymentType"],
                    marital_status=user_data["MaritalStatus"],
                    has_mortgage=user_data["HasMortgage"],
                    has_dependents=user_data["HasDependents"],
                    has_cosigner=user_data["HasCoSigner"],
                    prediction_result=prediction,
                    prediction_probability=probability,
                )
            
            messages.success(request, "Loan Application Submitted Successfully")
            
            # Re-render the page with XAI results instead of redirecting
            context = {
                "prediction": prediction,
                "probability": probability,
                "probability_pct": round(probability * 100, 1) if probability else 0,
                "user_data": user_data,
                **xai_context,
            }
            return render(request, "User/apply.html", context)
            
        except (ValueError, KeyError) as e:
            messages.error(request, f"Error processing form: {str(e)}")
            return redirect("apply_loan")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
            return redirect("apply_loan")
    
    # GET request - show empty form
    return render(request, "User/apply.html", {
        "prediction": prediction, 
        "probability": probability
    })


# -------------------------------
# Loan Applications List (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def loan_applications(request):
    applications = LoanApplication.objects.all().order_by('-created_at')
    
    total = applications.count()
    pending = applications.filter(status="PENDING").count()
    approved = applications.filter(status="APPROVED").count()
    rejected = applications.filter(status="REJECTED").count()
    cleared = applications.filter(status="CLEARED").count()
    
    # Search by user ID or name
    search = request.GET.get("search")
    if search:
        applications = applications.filter(
            user__full_name__icontains=search
        ) | applications.filter(
            user__id__icontains=search
        )
    
    # Filter by status
    status_filter = request.GET.get("status")
    if status_filter and status_filter != "ALL":
        applications = applications.filter(status=status_filter)
    
    context = {
        "applications": applications,
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "cleared": cleared,
        "current_status": status_filter or "ALL",
        "search_term": search or "",
    }
    
    return render(request, "Banker/loan_applications.html", context)


# -------------------------------
# Approve Loan (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def approve_loan(request, id):
    loan = get_object_or_404(LoanApplication, id=id)
    loan.status = "APPROVED"
    loan.save()
    messages.success(request, f"Loan #{id} has been approved.")
    return redirect("loan_applications")


# -------------------------------
# Reject Loan (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def reject_loan(request, id):
    loan = get_object_or_404(LoanApplication, id=id)
    loan.status = "REJECTED"
    loan.save()
    messages.error(request, f"Loan #{id} has been rejected.")
    return redirect("loan_applications")


# -------------------------------
# Clear Loan (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def clear_loan(request, id):
    loan = get_object_or_404(LoanApplication, id=id)
    loan.status = "CLEARED"
    loan.save()
    messages.success(request, f"Loan #{id} has been marked as cleared.")
    return redirect("loan_applications")


# -------------------------------
# Delete Application (User)
# -------------------------------
@login_required
def delete_application(request, id):
    loan = get_object_or_404(LoanApplication, id=id, user=request.user)
    
    if loan.status == "CLEARED":
        loan.delete()
        messages.success(request, "Application Deleted Successfully")
    else:
        messages.error(request, "Loan must be cleared first before deletion")
    
    return redirect("user_dashboard")


# -------------------------------
# View Single Loan Application (Banker)
# -------------------------------
# -------------------------------
# View Single Loan Application (Banker)
# -------------------------------
@login_required
@role_required(allowed_roles=["BANKER"])
def view_loan_details(request, id):
    """
    Display the full details of a single loan application for bankers.
    Shows all form data submitted by the user, prediction results,
    submission time, and action buttons based on current status.
    """
    # Fetch the loan or return 404 if not found
    loan = get_object_or_404(LoanApplication, id=id)

    context = {
        "loan": loan
    }

    return render(request, "Banker/view_loan_details.html", context)

# -------------------------------
# Delete Loan Record (Banker)

def delete_loan(request, loan_id):

    loan = get_object_or_404(LoanApplication, id=loan_id)

    if loan.status in ["CLEARED", "REJECTED"]:
        loan.delete()
        messages.success(request, "Loan record deleted successfully.")
    else:
        messages.error(request, "Only cleared or rejected loans can be deleted.")

    return redirect("loan_applications")