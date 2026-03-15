from django.db import models
from agency_admin.models import Car
from users.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
class CarReview(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='car_reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['car', 'user']
    
from django.db import models
from django.contrib.auth import get_user_model
from agency_admin.models import Car, ExtraService
User = get_user_model()

class RentalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('quotation_sent', 'Quotation Sent'),
        ('awaiting_payment', 'Awaiting Payment'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='rental_requests')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rental_requests')
    pickup_date = models.DateTimeField()
    return_date = models.DateTimeField()
    notes = models.TextField(blank=True)
    extra_services = models.ManyToManyField(ExtraService, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_intent_id = models.CharField(max_length=255, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    checkin_current_step = models.PositiveSmallIntegerField(default=1)
    checkin_completed = models.BooleanField(default=False)

    billing_same_as_customer = models.BooleanField(default=True)
    billing_full_name = models.CharField(max_length=255, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)

    document_type = models.CharField(max_length=50, blank=True)
    document_number = models.CharField(max_length=100, blank=True)
    document_expiry_date = models.DateField(null=True, blank=True)
    document_verified = models.BooleanField(default=False)
    document_front_image = models.ImageField(upload_to='checkin_documents/front/', null=True, blank=True)
    document_back_image = models.ImageField(upload_to='checkin_documents/back/', null=True, blank=True)

    checkin_starting_km = models.PositiveIntegerField(null=True, blank=True)
    checkin_fuel_level = models.CharField(max_length=50, blank=True)
    checkin_car_condition = models.CharField(max_length=100, blank=True)
    checkin_inspection_notes = models.TextField(blank=True)

    inspection_photos = models.JSONField(default=list, blank=True)

    checkin_completed_at = models.DateTimeField(null=True, blank=True)
    checkin_completed_by = models.ForeignKey(
        'users.AgencyAgent', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='checkins_completed'
    )

    # CARGO sync (placeholder)
    cargo_sync_status = models.CharField(max_length=50, default="Not Synced", blank=True)
    

# Checkout tracking
    checkout_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='pending'
    )
    checkout_current_step = models.PositiveSmallIntegerField(default=1)  # 1–3
    checkout_completed_at = models.DateTimeField(null=True, blank=True)
    checkout_completed_by = models.ForeignKey(
        'users.AgencyAgent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkouts_completed'
    )

    # Checkout inspection data
    checkout_ending_km = models.PositiveIntegerField(null=True, blank=True)
    checkout_fuel_level = models.CharField(max_length=50, blank=True)  # Full, 3/4, etc.
    checkout_car_condition = models.CharField(max_length=100, blank=True)
    checkout_damage_notes = models.TextField(blank=True)
    checkout_return_photos = models.JSONField(default=list, blank=True)  # list of photo paths

    # Extra charges (step 2)
    checkout_damage_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkout_late_return_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkout_extra_km_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkout_fuel_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkout_cleaning_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    checkout_extra_charge_notes = models.TextField(blank=True)

    # Final invoice snapshot (step 3)
    checkout_final_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    checkout_invoice_sent = models.BooleanField(default=False)
    checkout_invoice_sent_at = models.DateTimeField(null=True, blank=True)        
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.customer.email} - {self.car.car_name}"
    
    @property
    def total_days(self):
        days = (self.return_date - self.pickup_date).days
        return days if days > 0 else 1

class Payment(models.Model):
    rental_request = models.OneToOneField(RentalRequest, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_intent_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment for {self.rental_request.id}"