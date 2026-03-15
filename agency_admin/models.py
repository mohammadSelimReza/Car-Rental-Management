from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from users.models import Agency, AgencyAgent
User = get_user_model()
class Car(models.Model):
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='cars')
    car_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50)
    transmission = models.CharField(max_length=50)
    fuel_type = models.CharField(max_length=50)
    seats = models.PositiveSmallIntegerField()
    doors = models.PositiveSmallIntegerField()
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, default='available')
    featured_image = models.ImageField(upload_to='car_images/')
    features = models.JSONField(default=list, blank=True)
    color = models.CharField(max_length=50, null=True, blank=True)
    assigned_agent = models.ForeignKey(
        AgencyAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cars'
    )
    license_plate=models.CharField(max_length=20, unique=True, null=True, blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.car_name}"
    
    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(sum(review.rating for review in reviews) / reviews.count(), 1)
        return 0.0
    
    @property
    def total_reviews(self):
        
        return self.reviews.count()


class ExtraService(models.Model):
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='extra_services')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_per_day = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - ${self.price_per_day}/day"
    
    

