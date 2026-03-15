from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('agency_agent', 'Agency Agent'),
        ('agency_admin', 'Agency Admin'),
        ('super_admin', 'Super Admin'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    otp = models.CharField(max_length=6, null=True, blank=True)
    
    def __str__(self):
        return f"{self.username} ({self.role})"
    

class Customer(models.Model):
    LICENSE_STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('verified', 'Verified'),
        ('pending', 'Pending Review'),
        ('rejected', 'Rejected'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    name = models.CharField(max_length=255)
    profile_photo = models.ImageField(
            upload_to='customer_photos/',
            null=True,
            blank=True,
            help_text="Customer profile picture"
        )
    license_image = models.ImageField(upload_to='licenses/')
    license_number = models.CharField(max_length=100, unique=True)
    license_expiry_date = models.DateField()
    license_front_image = models.ImageField(upload_to='customer_licenses/front/', blank=True, null=True)
    license_back_image = models.ImageField(upload_to='customer_licenses/back/', blank=True, null=True)
    id_passport_number = models.CharField(max_length=100, unique=True)
    license_rejection_reason = models.TextField(blank=True, null=True)
    license_verified_at = models.DateTimeField(null=True, blank=True)
    license_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    license_status = models.CharField(
        max_length=20, 
        choices=LICENSE_STATUS_CHOICES, 
        default='not_submitted'
    )
    vip_status = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_flagged = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    def __str__(self):
        return self.name
    

class Agency(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('disabled', 'Disabled'),
        ('suspended', 'Suspended'),
    )
    name = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to='agency_logos/', null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    terms_and_conditions = models.TextField(null=True, blank=True)
    privacy_policy = models.TextField(null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default="United States")

    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)

    email_notifications = models.BooleanField(default=True, help_text="Receive general email notifications")
    booking_alerts = models.BooleanField(default=False, help_text="Alerts for new bookings")
    maintenance_alerts = models.BooleanField(default=True, help_text="Vehicle maintenance reminders")
    payment_notifications = models.BooleanField(default=True, help_text="Notifications for payments received")
    late_return_alerts = models.BooleanField(default=True, help_text="Alerts for late vehicle returns")

    account_type = models.CharField(max_length=50, default="Agency", editable=False)
    permission_level = models.CharField(max_length=50, default="Agency Admin", editable=False)
    account_status = models.CharField(max_length=20, default="Active", editable=False)
    member_since = models.DateTimeField(default=timezone.now, editable=False,null=True, blank=True)

    api_status = models.CharField(max_length=20, default="Connected", editable=False)
    last_sync = models.DateTimeField(null=True, blank=True, editable=False)
    pricing_base_model = models.CharField(max_length=100, default="Standard", editable=False)
    currency = models.CharField(max_length=3, default="USD", editable=False)
    
    stripe_connect_account_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_onboarding_completed = models.BooleanField(default=False)
    stripe_account_status = models.CharField(max_length=50, default="not_connected")
    is_active = models.BooleanField(default=True)
    suspension_reason = models.TextField(blank=True, null=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('users.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_agencies')
    def __str__(self):
        return self.name
    
    
class AgencyAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='admins')
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='admin_photos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.name} (Admin for {self.agency.name})"
    
class AgencyAgent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agent_profile')
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='agents', null=True, blank=True)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='agent_photos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} (Agent for {self.agency.name if self.agency else 'No Agency'})"