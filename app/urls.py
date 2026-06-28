from django.urls import path
from . import views

urlpatterns = [

    # Home
    path("", views.home, name="home"),

    # Authentication
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Dashboards
    path("user-dashboard/", views.user_dashboard, name="user_dashboard"),
    path("banker-dashboard/", views.banker_dashboard, name="banker_dashboard"),

    # KYC
    path("kyc/", views.kyc_form, name="kyc_form"),
    path("kyc-applications/", views.kyc_applications, name="kyc_applications"),
    path(
        "kyc/<int:kyc_id>/<str:action>/",
        views.update_kyc_status,
        name="update_kyc_status"
    ),
    path("kyc/<int:kyc_id>/", views.view_kyc, name="view_kyc"),

    # Loan (User)
    path("apply-loan/", views.apply_loan, name="apply_loan"),
    path("delete-application/<int:id>/", views.delete_application, name="delete_application"),

    # Loan (Banker)
    path("loan-applications/", views.loan_applications, name="loan_applications"),
    path("approve-loan/<int:id>/", views.approve_loan, name="approve_loan"),
    path("reject-loan/<int:id>/", views.reject_loan, name="reject_loan"),
    path("clear-loan/<int:id>/", views.clear_loan, name="clear_loan"),
    path("loan/<int:id>/", views.view_loan_details, name="view_loan_details"),
    path('delete-loan/<int:loan_id>/', views.delete_loan, name='delete_loan'),
]