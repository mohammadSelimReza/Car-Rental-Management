from rest_framework import serializers
from .models import RentalRequest
from agency_admin.models import Car, ExtraService

class ExtraServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraService
        fields = ['id', 'name', 'price_per_day']

class CarListSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name')
    agency_location = serializers.CharField(source='agency.location')
    featured_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Car
        fields = [
            'id', 'car_name', 'category', 'price_per_day', 'transmission',
            'fuel_type', 'seats', 'doors', 'featured_image_url',
            'agency_name', 'agency_location', 'average_rating', 'total_reviews'
        ]
    
    def get_featured_image_url(self, obj):
        request = self.context.get('request')
        if obj.featured_image and request:
            return request.build_absolute_uri(obj.featured_image.url)
        return None

class CarDetailSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name')
    agency_location = serializers.CharField(source='agency.location')
    featured_image_url = serializers.SerializerMethodField()
    available_services = serializers.SerializerMethodField()
    
    class Meta:
        model = Car
        fields = [
            'id', 'car_name', 'category', 'price_per_day', 'transmission',
            'fuel_type', 'seats', 'doors', 'status', 'features',
            'featured_image_url', 'agency_name', 'agency_location',
            'available_services', 'average_rating', 'total_reviews'
        ]
    
    def get_featured_image_url(self, obj):
        request = self.context.get('request')
        if obj.featured_image and request:
            return request.build_absolute_uri(obj.featured_image.url)
        return None
    
    def get_available_services(self, obj):
        services = ExtraService.objects.filter(agency=obj.agency, is_active=True)
        return ExtraServiceSerializer(services, many=True).data

class CreateRentalRequestSerializer(serializers.Serializer):
    car_id = serializers.IntegerField()
    pickup_date = serializers.DateTimeField()
    return_date = serializers.DateTimeField()
    service_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False, 
        default=list
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        from django.utils import timezone
        
        if data['pickup_date'] <= timezone.now():
            raise serializers.ValidationError("Pickup date must be in the future")
        
        if data['return_date'] <= data['pickup_date']:
            raise serializers.ValidationError("Return date must be after pickup date")
        
        car = Car.objects.get(id=data['car_id'])
        conflicting = RentalRequest.objects.filter(
            car=car,
            status__in=['pending', 'approved'],
            pickup_date__lt=data['return_date'],
            return_date__gt=data['pickup_date']
        )
        
        if conflicting.exists():
            raise serializers.ValidationError("Car not available for selected dates")
        
        return data

from agency_agent.models import Quotation

class QuotationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        exclude = ['rental_request', 'created_by']
        
class RentalRequestSerializer(serializers.ModelSerializer):
    car_details = CarListSerializer(source='car', read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    selected_services = ExtraServiceSerializer(source='extra_services', many=True, read_only=True)
    service_ids = serializers.PrimaryKeyRelatedField(
        source='extra_services',
        queryset=ExtraService.objects.all(),
        many=True,
        write_only=True,
        required=False
    )
    total_days = serializers.IntegerField(read_only=True)
    car_price_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    extra_services_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    quotation = QuotationDetailSerializer(read_only=True) 
    class Meta:
        model = RentalRequest
        fields = [
            'id', 'car', 'car_details', 'customer', 'customer_name', 'customer_email',
            'pickup_date', 'return_date', 'total_days', 'car_price_total',
            'selected_services', 'service_ids', 'extra_services_total', 'total_price',
            'notes', 'status', 'payment_status', 'created_at', 'quotation'
        ]
        read_only_fields = ['id', 'customer', 'created_at', 'status', 'payment_status']
    
    def create(self, validated_data):
        extra_services = validated_data.pop('extra_services', [])
        rental_request = RentalRequest.objects.create(**validated_data)
        rental_request.extra_services.set(extra_services)
        return rental_request
    
    def update(self, instance, validated_data):
        extra_services = validated_data.pop('extra_services', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if extra_services is not None:
            instance.extra_services.set(extra_services)
        instance.save()
        return instance

class PaymentIntentSerializer(serializers.Serializer):
    rental_request_id = serializers.IntegerField()
    
    
from users.models import Customer
class LicenseDetailSerializer(serializers.ModelSerializer):
    license_front_url = serializers.SerializerMethodField(read_only=True)
    license_back_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'license_number',
            'license_expiry_date',
            'license_status',
            'license_rejection_reason',
            'license_front_image',
            'license_front_url',
            'license_back_image',
            'license_back_url',
            'license_verified_at'
        ]

    def get_license_front_url(self, obj):
        request = self.context.get('request')
        if obj.license_front_image:
            return request.build_absolute_uri(obj.license_front_image.url) if request else obj.license_front_image.url
        return None

    def get_license_back_url(self, obj):
        request = self.context.get('request')
        if obj.license_back_image:
            return request.build_absolute_uri(obj.license_back_image.url) if request else obj.license_back_image.url
        return None


class LicenseUpdateSerializer(serializers.ModelSerializer):
    license_front_image = serializers.ImageField(required=False, allow_null=True)
    license_back_image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Customer
        fields = [
            'license_number',
            'license_expiry_date',
            'license_front_image',
            'license_back_image'
        ]

    def validate(self, data):
        if self.instance.license_status == 'not_submitted':
            if not data.get('license_front_image') or not data.get('license_back_image'):
                raise serializers.ValidationError({
                    "license_front_image": "Both front and back images are required for first submission.",
                    "license_back_image": "Both front and back images are required for first submission."
                })
        return data

    def update(self, instance, validated_data):
        instance.license_status = 'pending'
        instance.license_rejection_reason = None
        instance.license_verified_at = None
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class CustomerProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.CharField(source='phone_number', read_only=True)

    profile_photo_url = serializers.SerializerMethodField(read_only=True)

    license_status = serializers.CharField(read_only=True)
    license_verified = serializers.BooleanField(default=False, read_only=True, source='license_status')

    class Meta:
        model = Customer
        fields = [
            'full_name', 'email', 'phone',
            'profile_photo', 'profile_photo_url',
            'license_status', 'license_verified'
        ]

    def get_profile_photo_url(self, obj):
        request = self.context.get('request')
        if obj.profile_photo:
            return request.build_absolute_uri(obj.profile_photo.url) if request else obj.profile_photo.url
        return None


class CustomerProfileUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', required=False)
    phone = serializers.CharField(source='phone_number', required=False, allow_blank=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Customer
        fields = ['full_name', 'phone', 'profile_photo']

    def validate_profile_photo(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB max
                raise serializers.ValidationError("Image size too large (max 5MB)")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
from agency_agent.models import Fine
class FineSerializer(serializers.ModelSerializer):
    invoice_url = serializers.SerializerMethodField(read_only=True)
    vehicle_name = serializers.CharField(source='rental_request.car.car_name', read_only=True)
    booking_id = serializers.CharField(source='rental_request.id', read_only=True)

    class Meta:
        model = Fine
        fields = [
            'id', 'fine_type', 'reason', 'amount', 'due_date',
            'status', 'invoice_url', 'vehicle_name', 'booking_id'
        ]

    def get_invoice_url(self, obj):
        request = self.context.get('request')
        if obj.invoice_file:
            return request.build_absolute_uri(obj.invoice_file.url) if request else obj.invoice_file.url
        return None
    
    
class FinePaymentSerializer(serializers.ModelSerializer):
    client_secret = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Fine
        fields = ['id', 'amount', 'status', 'client_secret']

    def get_client_secret(self, obj):
        return None