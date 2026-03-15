from decimal import Decimal

from rest_framework import serializers
from customers . models import RentalRequest
        
from super_admin.models import GlobalPricingRule
from .models import Fine, Quotation

class CreateQuotationSerializer(serializers.Serializer):
    insurance_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    security_deposit = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    notes_for_customer = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        pricing_rules = GlobalPricingRule.objects.first()
        if pricing_rules and 'discount_amount' in data:
            rental_request = self.context['rental_request']
            base_price = rental_request.total_days * rental_request.car.price_per_day
            max_discount = base_price * (pricing_rules.max_discount_limit / 100)
            if data['discount_amount'] > max_discount:
                raise serializers.ValidationError(f"Discount cannot exceed ${max_discount:.2f}")
        return data

class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = '__all__'

from users.models import User
class CustomerCardSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='customer_profile.name', read_only=True)

    class Meta:
        model = User
        fields = ['full_name']

from agency_admin.models import Car, ExtraService
class CarCardSerializer(serializers.ModelSerializer):
    featured_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Car
        fields = [
            'car_name',
            'featured_image_url',
            'average_rating',
            'seats',
            'transmission'
        ]

    def get_featured_image_url(self, obj):
        request = self.context.get('request')
        if obj.featured_image and request:
            return request.build_absolute_uri(obj.featured_image.url)
        return None

class AgentRentalRequestCardSerializer(serializers.ModelSerializer):
    customer = CustomerCardSerializer(read_only=True)
    car = CarCardSerializer(read_only=True)

    pickup_date_formatted = serializers.DateTimeField(
        source='pickup_date',
        format='%Y-%m-%d',
        read_only=True
    )

    return_date_formatted = serializers.DateTimeField(
        source='return_date',
        format='%Y-%m-%d',
        read_only=True
    )
    pickup_location = serializers.CharField(source='car.agency.location', read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'id',
            'customer',
            'car',
            'pickup_date_formatted',
            'return_date_formatted',
            'pickup_location',
            'notes',
            'status',
        ]

from agency_admin.models import ExtraService
class ExtraServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraService
        fields = ['id', 'name', 'price_per_day']

from users.models import Customer        
class CustomerDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    license_status = serializers.CharField()

    class Meta:
        model = Customer
        fields = ['name', 'license_status']
        
class AgentRentalRequestDetailSerializer(serializers.ModelSerializer):
    customer_info = CustomerDetailSerializer(source='customer.customer_profile', read_only=True)
    car_name = serializers.CharField(source='car.car_name', read_only=True)
    pickup_location = serializers.CharField(source='car.agency.location', read_only=True)
    duration_days = serializers.IntegerField(source='total_days', read_only=True)
    booking_id = serializers.CharField(source='id', read_only=True)
    
    available_extra_services = serializers.SerializerMethodField()
    selected_extra_services = ExtraServiceSerializer(source='extra_services', many=True, read_only=True)
    pricing_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'booking_id', 'customer_info', 'car_name', 'pickup_date', 'return_date',
            'pickup_location', 'duration_days','status', 'available_extra_services', 
            'selected_extra_services', 'pricing_breakdown'
        ]
        
    def get_available_extra_services(self, obj):
        agency = obj.car.agency
        services = ExtraService.objects.filter(agency=agency, is_active=True)
        return ExtraServiceSerializer(services, many=True).data

    def get_pricing_breakdown(self, obj: RentalRequest) -> dict:
        if hasattr(obj, 'quotation') and obj.quotation:
            q = obj.quotation
            
            return {
                "base_price":           q.base_price,
                "insurance_cost":       q.insurance_cost,
                "extra_services_cost":  q.extra_services_cost,
                "subtotal":             q.subtotal,
                "vat_percentage":       q.vat_percentage,
                "vat_amount":           q.vat_amount,
                "discount":             q.discount_amount,
                "security_deposit":     q.security_deposit,
                "total_price":          q.total_price,
                "is_final":             True,
                "notes":                q.notes_for_customer or ""
            }
        rules = GlobalPricingRule.objects.first() or GlobalPricingRule()
        
        base_price = obj.total_days * obj.car.price_per_day
        extra_cost = sum(obj.total_days * s.price_per_day for s in obj.extra_services.all())
        
        subtotal         = base_price + extra_cost
        vat_pct          = rules.default_vat_tax
        vat_amount       = subtotal * (vat_pct / Decimal('100'))
        security_deposit = rules.default_security_deposit
        
        preliminary_total = subtotal + vat_amount

        return {
            "base_price":           base_price,
            "insurance_cost":       Decimal('0.00'),
            "extra_services_cost":  extra_cost,
            "subtotal":             subtotal,
            "vat_percentage":       vat_pct,
            "vat_amount":           vat_amount,
            "discount":             Decimal('0.00'),
            "security_deposit":     security_deposit,
            "total_price":          preliminary_total,
            "is_final":             False,
            "notes":                ""
        }


        
class RejectRequestSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(
        required=True, 
        allow_blank=False, 
        max_length=500,
        error_messages={'required': 'A rejection reason is required.', 'blank': 'Rejection reason cannot be empty.'}
    )
    
    

class CustomerCheckinSerializer(serializers.ModelSerializer):
    full_name=serializers.SerializerMethodField()
    phone_number=serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number']

    def get_full_name(self, obj):
        try:
            return obj.customer_profile.name or "Unnamed"
        except AttributeError:
            return "No Customer Profile"
    def get_phone_number(self, obj):
        try:
            return obj.customer_profile.phone_number or "No Phone"
        except AttributeError:
            return "No Customer Profile"

class BillingInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalRequest
        fields = [
            'billing_same_as_customer',
            'billing_full_name',
            'billing_email',
            'billing_phone',
            'billing_address',
            'billing_city',
            'billing_country'
        ]


class DocumentCheckinSerializer(serializers.ModelSerializer):
    document_front_url = serializers.SerializerMethodField()
    document_back_url = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'document_type',
            'document_number',
            'document_expiry_date',
            'document_verified',
            'document_front_image',
            'document_front_url',
            'document_back_image',
            'document_back_url'
        ]

    def get_document_front_url(self, obj):
        request = self.context.get('request')
        if obj.document_front_image:
            if request:
                return request.build_absolute_uri(obj.document_front_image.url)
            return obj.document_front_image.url
        return None

    def get_document_back_url(self, obj):
        request = self.context.get('request')
        if obj.document_back_image:
            if request:
                return request.build_absolute_uri(obj.document_back_image.url)
            return obj.document_back_image.url
        return None


class CarInspectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalRequest
        fields = [
            'checkin_starting_km',
            'checkin_fuel_level',
            'checkin_car_condition',
            'checkin_inspection_notes',
            'inspection_photos'
        ]


class PaymentDepositCheckinSerializer(serializers.ModelSerializer):
    rental_amount = serializers.SerializerMethodField()
    deposit_amount = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'rental_amount',
            'deposit_amount',
            'total_amount',
            'payment_status'
        ]

    def get_rental_amount(self, obj):
        if obj.quotation:
            return obj.quotation.total_price
        return Decimal('0.00')

    def get_deposit_amount(self, obj):
        if obj.quotation:
            return obj.quotation.security_deposit
        return Decimal('0.00')

    def get_total_amount(self, obj):
        rental = Decimal('0.00')
        deposit = Decimal('0.00')

        if obj.quotation:
            rental = obj.quotation.total_price or Decimal('0.00')
            deposit = obj.quotation.security_deposit or Decimal('0.00')

        return rental + deposit

from django.core.files.storage import default_storage
class BookingSummarySerializer(serializers.ModelSerializer):
    customer = CustomerCheckinSerializer()
    vehicle = serializers.CharField(source='car.car_name', read_only=True)
    location = serializers.CharField(source='car.agency.location', read_only=True)

    pickup_date = serializers.DateTimeField(
        format='%m/%d/%Y %I:%M %p',
        read_only=True
    )

    return_date = serializers.DateTimeField(
        format='%m/%d/%Y',
        read_only=True
    )

    agent = serializers.CharField(
        source='car.assigned_agent.name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = RentalRequest
        fields = [
            'id',
            'customer',
            'vehicle',
            'pickup_date',
            'return_date',
            'location',
            'agent'
        ]

class CheckinFullSerializer(serializers.ModelSerializer):
    customer = CustomerCheckinSerializer()
    payment = PaymentDepositCheckinSerializer(source='*', read_only=True)

    billing_same_as_customer = serializers.BooleanField(required=False)
    billing_full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    billing_email = serializers.EmailField(required=False, allow_blank=True)
    billing_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    billing_address = serializers.CharField(required=False, allow_blank=True)
    billing_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    billing_country = serializers.CharField(max_length=100, required=False, allow_blank=True)

    document_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    document_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    document_expiry_date = serializers.DateField(required=False, allow_null=True)
    document_verified = serializers.BooleanField(required=False, default=False)

    document_front_image = serializers.ImageField(required=False, allow_null=True)
    document_back_image = serializers.ImageField(required=False, allow_null=True)

    document_front_url = serializers.SerializerMethodField(read_only=True)
    document_back_url = serializers.SerializerMethodField(read_only=True)

    checkin_starting_km = serializers.IntegerField(required=False, allow_null=True)
    checkin_fuel_level = serializers.CharField(max_length=50, required=False, allow_blank=True)
    checkin_car_condition = serializers.CharField(max_length=100, required=False, allow_blank=True)
    checkin_inspection_notes = serializers.CharField(required=False, allow_blank=True)

    # return stored list
    inspection_photos = serializers.SerializerMethodField()

    cargo_sync_status = serializers.CharField(read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'id', 'customer',

            'billing_same_as_customer', 'billing_full_name', 'billing_email',
            'billing_phone', 'billing_address', 'billing_city', 'billing_country',

            'document_type', 'document_number', 'document_expiry_date',
            'document_verified',

            'document_front_image', 'document_front_url',
            'document_back_image', 'document_back_url',

            'checkin_starting_km', 'checkin_fuel_level',
            'checkin_car_condition', 'checkin_inspection_notes',

            'inspection_photos',

            'payment',

            'cargo_sync_status',
            'checkin_current_step',
            'checkin_completed'
        ]

    def get_document_front_url(self, obj):
        request = self.context.get('request')
        if obj.document_front_image:
            if request:
                return request.build_absolute_uri(obj.document_front_image.url)
            return obj.document_front_image.url
        return None

    def get_document_back_url(self, obj):
        request = self.context.get('request')
        if obj.document_back_image:
            if request:
                return request.build_absolute_uri(obj.document_back_image.url)
            return obj.document_back_image.url
        return None

    def update(self, instance, validated_data):

        request = self.context.get("request")

        # update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # handle multiple inspection photos
        photos = request.FILES.getlist("inspection_photos")

        if photos:
            existing = instance.inspection_photos or []

            for photo in photos:
                saved_path = default_storage.save(
                    f"inspection_photos/{photo.name}",
                    photo
                )
                existing.append(saved_path)

            instance.inspection_photos = existing

        instance.save()
        return instance

    def get_inspection_photos(self, obj):
        request = self.context.get("request")

        if not obj.inspection_photos:
            return []

        urls = []

        for photo in obj.inspection_photos:
            if request:
                urls.append(request.build_absolute_uri(f"/media/{photo}"))
            else:
                urls.append(f"/media/{photo}")

        return urls
    

class CheckoutInspectionSerializer(serializers.ModelSerializer):
    checkout_return_photos_urls = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'checkout_ending_km', 'checkout_fuel_level',
            'checkout_car_condition', 'checkout_damage_notes',
            'checkout_return_photos', 'checkout_return_photos_urls'
        ]

    def get_checkout_return_photos_urls(self, obj):
        request = self.context.get('request')
        urls = []
        for path in obj.checkout_return_photos or []:
            if request:
                urls.append(request.build_absolute_uri(path))
            else:
                from django.conf import settings
                urls.append(f"{settings.MEDIA_URL.rstrip('/')}{path}")
        return urls


class CheckoutExtraChargesSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalRequest
        fields = [
            'checkout_damage_charge', 'checkout_late_return_charge',
            'checkout_extra_km_charge', 'checkout_fuel_charge',
            'checkout_cleaning_fee', 'checkout_extra_charge_notes'
        ]


class CheckoutInvoiceSerializer(serializers.ModelSerializer):
    final_total = serializers.ReadOnlyField(source='checkout_final_total')
    invoice_sent = serializers.BooleanField(source='checkout_invoice_sent', read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'final_total', 'invoice_sent',
            'checkout_damage_charge', 'checkout_late_return_charge',
            'checkout_extra_km_charge', 'checkout_fuel_charge',
            'checkout_cleaning_fee'
        ]

from django.core.files.storage import default_storage
from django.conf import settings
class CheckOutFullSerializer(serializers.ModelSerializer):
    
    customer_name = serializers.CharField(
        source="customer.email",
        read_only=True
    )

    vehicle_name = serializers.CharField(
        source="car.car_name",
        read_only=True
    )

    checkout_return_photos_urls = serializers.SerializerMethodField()

    checkout_return_photos = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = RentalRequest
        fields = [

            "id",
            "customer_name",
            "vehicle_name",

            "checkout_current_step",
            "checkout_status",

            "checkout_ending_km",
            "checkout_fuel_level",
            "checkout_car_condition",
            "checkout_damage_notes",
            "checkout_return_photos",
            "checkout_return_photos_urls",

            "checkout_damage_charge",
            "checkout_late_return_charge",
            "checkout_extra_km_charge",
            "checkout_fuel_charge",
            "checkout_cleaning_fee",
            "checkout_extra_charge_notes",

            "checkout_final_total",
            "checkout_invoice_sent",
        ]

        read_only_fields = [
            "checkout_final_total",
            "checkout_invoice_sent",
        ]

    def get_checkout_return_photos_urls(self, obj):

        request = self.context.get("request")

        if not obj.checkout_return_photos:
            return []

        urls = []

        for path in obj.checkout_return_photos:

            if request:
                urls.append(
                    request.build_absolute_uri(
                        settings.MEDIA_URL + path
                    )
                )
            else:
                urls.append(settings.MEDIA_URL + path)

        return urls

    def update(self, instance, validated_data):

        request = self.context.get("request")

        photos = validated_data.pop("checkout_return_photos", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if photos:

            existing_photos = instance.checkout_return_photos or []

            for photo in photos:

                saved_path = default_storage.save(
                    f"checkout_return_photos/{photo.name}",
                    photo
                )

                existing_photos.append(saved_path)

            instance.checkout_return_photos = existing_photos

        instance.save()
        return instance
    
    
class FineCreateSerializer(serializers.ModelSerializer):
    rental_request_id = serializers.PrimaryKeyRelatedField(
        queryset=RentalRequest.objects.all(),
        source='rental_request',
        write_only=True
    )
    fine_document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = Fine
        fields = [
            'rental_request_id',
            'fine_type',
            'amount',
            'due_date',
            'fine_document',
            'additional_note'
        ]

    def validate_rental_request_id(self, value):
        # Ensure the booking is assigned to this agent
        agent = self.context['request'].user.agent_profile
        if not value.car.assigned_agent == agent:
            raise serializers.ValidationError("You can only create fines for bookings assigned to you")
        return value

    def create(self, validated_data):
        # Auto-set created_by to current agent
        validated_data['created_by'] = self.context['request'].user.agent_profile
        return super().create(validated_data)


class FineListSerializer(serializers.ModelSerializer):
    booking_id = serializers.CharField(source='rental_request.id', read_only=True)
    customer_name = serializers.CharField(source='rental_request.customer.name', read_only=True)
    vehicle_name = serializers.CharField(source='rental_request.car.car_name', read_only=True)
    fine_document_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Fine
        fields = [
            'id', 'booking_id', 'customer_name', 'vehicle_name',
            'fine_type', 'amount', 'due_date', 'status',
            'paid_amount', 'fine_document_url', 'additional_note'
        ]

    def get_fine_document_url(self, obj):
        request = self.context.get('request')
        if obj.fine_document:
            return request.build_absolute_uri(obj.fine_document.url) if request else obj.fine_document.url
        return None
    
from .models import AgencyAgent


class AgentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.CharField(source='phone_number', required=False, allow_blank=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    agency_verified = serializers.BooleanField(source='agency.verified', read_only=True, default=True)
    
    # Profile photo URL
    profile_photo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AgencyAgent
        fields = [
            'full_name', 'email', 'phone',
            'agency_name', 'agency_verified',
            'profile_photo', 'profile_photo_url'
        ]

    def get_profile_photo_url(self, obj):
        request = self.context.get('request')
        if obj.profile_photo:
            return request.build_absolute_uri(obj.profile_photo.url) if request else obj.profile_photo.url
        return None 


class AgentProfileUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', required=False)
    phone = serializers.CharField(source='phone_number', required=False, allow_blank=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = AgencyAgent
        fields = ['full_name', 'phone', 'profile_photo']
        

class DashboardBookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vehicle_name = serializers.CharField(source='car.car_name', read_only=True)
    
    # Show check-in or check-out time depending on context
    time = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RentalRequest
        fields = ['customer_name', 'vehicle_name', 'time']

    def get_time(self, obj):
        # If this is check-in list, use checkin_completed_at
        # If check-out list, use checkout_completed_at
        if hasattr(obj, 'checkin_completed_at') and obj.checkin_completed_at:
            return obj.checkin_completed_at.strftime('%I:%M %p')
        if hasattr(obj, 'checkout_completed_at') and obj.checkout_completed_at:
            return obj.checkout_completed_at.strftime('%I:%M %p')
        return "N/A"

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