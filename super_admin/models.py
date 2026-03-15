from django.db import models

class GlobalPricingRule(models.Model):
    default_vat_tax = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.0,
        help_text="Default VAT/Tax percentage (%)"
    )

    default_security_deposit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.0,
        help_text="Default security deposit amount ($)"
    )

    max_discount_limit = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.0,
        help_text="Maximum discount limit percentage (%)"
    )

    vip_discount_default = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.0,
        help_text="VIP discount default percentage (%)"
    )

    late_return_penalty = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.0,
        help_text="Late return penalty per hour ($/hour)"
    )

    cancellation_policy = models.TextField(
        blank=True,
        help_text="Cancellation policy rules"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='updated_pricing_rules'
    )
    
    class Meta:
        verbose_name = "Global Pricing Rule"
        verbose_name_plural = "Global Pricing Rules"
    
    def __str__(self):
        return f"Global Pricing Rules (Updated: {self.updated_at.date()})"


from users.models import Agency
class CommissionPayout(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved – Ready to Pay'),
        ('processing', 'Processing via Stripe'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    agency = models.ForeignKey(Agency, on_delete=models.PROTECT, related_name='payouts')
    
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()   # 1–12
    
    period_start = models.DateField()
    period_end = models.DateField()
    
    total_bookings = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=14, decimal_places=2)
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_payout = models.DecimalField(max_digits=14, decimal_places=2)

    stripe_transfer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payout_id = models.CharField(max_length=255, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-period_year', '-period_month', 'agency__name']
        unique_together = ['agency', 'period_year', 'period_month']
        verbose_name = "Agency Monthly Payout"
        verbose_name_plural = "Agency Monthly Payouts"

    def __str__(self):
        return f"{self.agency.name} — {self.period_year}-{self.period_month:02d}"

    def save(self, *args, **kwargs):
        if self.commission_amount is not None and self.processing_fee is not None:
            self.net_payout = self.commission_amount - self.processing_fee
        super().save(*args, **kwargs)



class PlatformSettings(models.Model):
    # General Settings
    platform_name = models.CharField(max_length=255, default="RentHub")
    support_email = models.EmailField(default="support@renthub.com")
    support_phone = models.CharField(max_length=20, default="+8801234567890")
    business_address = models.TextField(blank=True)
    platform_logo = models.ImageField(upload_to='platform_logos/', null=True, blank=True)

    # Cargo Settings
    enable_cargo_services = models.BooleanField(default=False, help_text="Allow cargo/goods transportation bookings")
    enable_tracking = models.BooleanField(default=False, help_text="Enable real-time shipment tracking")
    default_insurance = models.BooleanField(default=True, help_text="Include cargo insurance by default")

    default_carrier = models.CharField(max_length=100, default="FedEx", blank=True)
    base_shipping_rate = models.DecimalField(max_digits=10, decimal_places=2, default=15.00)
    charge_per_kg = models.DecimalField(max_digits=8, decimal_places=2, default=2.50)
    express_shipping_rate = models.DecimalField(max_digits=10, decimal_places=2, default=35.00)
    free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=500.00)

    max_weight_kg = models.PositiveIntegerField(default=50)
    max_dimensions_cm = models.CharField(max_length=50, default="100x100x100", help_text="L×W×H in cm")

    enable_standard_delivery = models.BooleanField(default=True)
    standard_delivery_days = models.CharField(max_length=50, default="5-7 business days")
    enable_express_delivery = models.BooleanField(default=False)
    express_delivery_days = models.CharField(max_length=50, default="2-3 business days")
    enable_same_day_delivery = models.BooleanField(default=False)
    same_day_delivery_description = models.CharField(max_length=100, default="Within 24 hours")
    
    terms_and_conditions = models.TextField(default="By signing up, you agree to our Terms and Conditions.")
    privacy_policy = models.TextField(default="By signing up, you agree to our Privacy Policy.")

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('users.User', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def __str__(self):
        return "Platform Global Settings"

    @classmethod
    def get_settings(cls):
        """Always get the first (and only) settings row"""
        settings_obj, created = cls.objects.get_or_create(pk=1)
        return settings_obj