from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager
)
from django.conf import settings
from PIL import Image


# ==========================
# Custom User Manager
# ==========================

class CustomUserManager(BaseUserManager):

    def create_user(self, email, full_name, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'BANKER')

        return self.create_user(email, full_name, phone_number, password, **extra_fields)


# ==========================
# Custom User Model
# ==========================

class CustomUser(AbstractBaseUser, PermissionsMixin):

    USER = 'USER'
    BANKER = 'BANKER'

    USER_TYPE_CHOICES = (
        (USER, 'User'),
        (BANKER, 'Banker'),
    )

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default=USER
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number']

    def __str__(self):
        return self.email


# ==========================
# KYC MODEL
# ==========================

class KYC(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    full_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)

    father_spouse_name = models.CharField(max_length=100)
    marital_status = models.CharField(max_length=20)

    mobile_number = models.CharField(max_length=15)
    email = models.EmailField()

    current_address = models.TextField()
    permanent_address = models.TextField()

    occupation_type = models.CharField(max_length=50)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2)
    source_of_funds = models.CharField(max_length=50)

    nature_of_business = models.CharField(max_length=100, blank=True, null=True)
    purpose_of_account = models.CharField(max_length=50)

    id_proof = models.FileField(upload_to='kyc/id_proofs/')
    photograph = models.ImageField(upload_to='kyc/photos/')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.photograph:
            img = Image.open(self.photograph.path)

            if img.height > 300 or img.width > 300:
                img = img.resize((300, 300))
                img.save(self.photograph.path)

    def __str__(self):
        return self.user.email


# ==========================
# LOAN APPLICATION MODEL
# ==========================

class LoanApplication(models.Model):

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CLEARED", "Cleared"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loan_applications"
    )

    age = models.IntegerField()
    income = models.FloatField()
    loan_amount = models.FloatField()
    credit_score = models.IntegerField()
    months_employed = models.IntegerField()
    num_credit_lines = models.IntegerField()
    interest_rate = models.FloatField()
    loan_term = models.IntegerField()
    dti_ratio = models.FloatField()

    EDUCATION_CHOICES = [
        ("Bachelor's", "Bachelor's"),
        ("Master's", "Master's"),
        ("High School", "High School"),
        ("PhD", "PhD"),
    ]

    EMPLOYMENT_CHOICES = [
        ("Full-time", "Full-time"),
        ("Unemployed", "Unemployed"),
        ("Self-employed", "Self-employed"),
        ("Part-time", "Part-time"),
    ]

    MARITAL_CHOICES = [
        ("Divorced", "Divorced"),
        ("Married", "Married"),
        ("Single", "Single"),
    ]

    YES_NO = [
        ("Yes", "Yes"),
        ("No", "No"),
    ]

    education = models.CharField(max_length=20, choices=EDUCATION_CHOICES)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES)
    marital_status = models.CharField(max_length=20, choices=MARITAL_CHOICES)
    has_mortgage = models.CharField(max_length=3, choices=YES_NO)
    has_dependents = models.CharField(max_length=3, choices=YES_NO)
    has_cosigner = models.CharField(max_length=3, choices=YES_NO)

    prediction_result = models.CharField(max_length=50, blank=True, null=True)
    prediction_probability = models.FloatField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - Loan #{self.id}"