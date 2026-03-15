from django.db import models
from django.utils import timezone
from customers.models import RentalRequest
from users.models import AgencyAgent

class Quotation(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    rental_request = models.OneToOneField(
        RentalRequest, 
        on_delete=models.CASCADE, 
        related_name='quotation'
    )
    created_by = models.ForeignKey(
        AgencyAgent, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='quotations'
    )
    
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    insurance_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    extra_services_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    notes_for_customer = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Quotation for Request ID: {self.rental_request.id}"
    
    
    
class Fine(models.Model):
    FINE_TYPE_CHOICES = [
        ('speeding_violation', 'Speeding Violation'),
        ('traffic_light_violation', 'Traffic Light Violation'),
        ('parking_violation', 'Parking Violation'),
        ('ztl_violation', 'ZTL Violation'),
        ('toll_violation', 'Toll Violation'),
        ('vehicle_damage', 'Vehicle Damage'),
        ('other', 'Other'),
    ]

    rental_request = models.ForeignKey(
        RentalRequest,
        on_delete=models.CASCADE,
        related_name='fines'
    )
    fine_type = models.CharField(
        max_length=50,
        choices=FINE_TYPE_CHOICES,
        default='other'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    fine_document = models.FileField(upload_to='fines_documents/', null=True, blank=True)
    invoice_file = models.FileField(upload_to='customer_invoices/', blank=True, null=True)
    additional_note = models.TextField(blank=True)
    
    created_by = models.ForeignKey(
        'users.AgencyAgent',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_fines'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('waived', 'Waived'),
            ('overdue', 'Overdue'),
        ],
        default='pending'
    )
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Fine {self.id} - {self.rental_request.id} - €{self.amount}"

    @property
    def is_overdue(self):
        return self.status == 'pending' and self.due_date < timezone.now().date()
