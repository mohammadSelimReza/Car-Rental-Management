from rest_framework import serializers
from django.db import transaction
from users.models import User, Agency, AgencyAgent

class AgentCreateSerializer(serializers.ModelSerializer):
    agent_email = serializers.EmailField(required=True, write_only=True)
    agent_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    agent_name = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = AgencyAgent
        fields = [
            'agent_name', 'phone_number', 'agent_email', 'agent_password'
        ]
    
    def validate_agent_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An agent with this email already exists.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        agent_email = validated_data.pop('agent_email')
        agent_password = validated_data.pop('agent_password')
        agent_name = validated_data.pop('agent_name')
        phone_number = validated_data.get('phone_number', '')

        agency = self.context.get('agency')
        if not agency:
            raise serializers.ValidationError("Agency information is missing.")
        
        agent_user = User.objects.create_user(
            username=agent_email,
            email=agent_email,
            password=agent_password,
            role='agency_agent'
        )
        
        agency_agent = AgencyAgent.objects.create(
            user=agent_user,
            agency=agency,
            name=agent_name,
            phone_number=phone_number,
        )
        
        return agency_agent
    
    
    
from .models import Car
class CarCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = [
            'id',
            'car_name',
            'price_per_day',
            'fuel_type',
            'assigned_agent',
            'status',
            'featured_image',
            'category',
            'transmission',
            'seats',
            'doors',
            'features'
        ]
    
    def create(self, validated_data):
        agency = self.context.get('agency')
        if not agency:
            raise serializers.ValidationError("Agency information is missing.")
        
        car = Car.objects.create(agency=agency, **validated_data)
        return car
    
    
from customers.models import Payment, RentalRequest
class AgentListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='phone_number', allow_null=True)
    initial = serializers.SerializerMethodField()
    assigned_cars_count = serializers.SerializerMethodField()
    active_bookings_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = AgencyAgent
        fields = [
            'id', 'full_name', 'initial',
            'email', 'phone',
            'assigned_cars_count', 'active_bookings_count',
            'status'
        ]

    def get_initial(self, obj):
        if obj.name:
            return obj.name[0].upper()
        return '?'

    def get_assigned_cars_count(self, obj):
        return obj.assigned_cars.count()

    def get_active_bookings_count(self, obj):
        return RentalRequest.objects.filter(
            car__assigned_agent=obj,
            status__in=['approved', 'awaiting_payment']
        ).count()

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"


class AgentUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', required=False)
    email = serializers.EmailField(source='user.email', required=False)
    phone = serializers.CharField(source='phone_number', allow_null=True, required=False)
    status = serializers.SerializerMethodField()

    class Meta:
        model = AgencyAgent
        fields = ['full_name', 'email', 'phone', 'status']
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        if 'email' in user_data:
            instance.user.email = user_data['email']
            instance.user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"
    
    

class CustomerInfoSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    vip_status = serializers.BooleanField(source='customer_profile.vip_status', read_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number','vip_status']

    def get_full_name(self, obj):
        try:
            return obj.customer_profile.name
        except AttributeError:
            return obj.get_full_name() or obj.username or "Unknown"

    def get_phone_number(self, obj):
        try:
            return obj.customer_profile.phone_number
        except AttributeError:
            return None


class VehicleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = ['car_name', 'license_plate', 'color']


class AgentInfoSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', read_only=True)

    class Meta:
        model = AgencyAgent
        fields = ['full_name']


class BookingListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vehicle = serializers.CharField(source='car.car_name', read_only=True)
    rental_dates = serializers.SerializerMethodField()
    agent_name = serializers.CharField(source='car.assigned_agent.name', allow_null=True, read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'id', 'customer_name', 'vehicle',
            'rental_dates', 'status', 'agent_name'
        ]

    def get_rental_dates(self, obj):
        start = obj.pickup_date.strftime('%b %d')
        end = obj.return_date.strftime('%b %d, %Y')
        return f"{start} - {end}"

class PaymentInfoSerializer(serializers.ModelSerializer):
    transaction_id = serializers.CharField(source='stripe_payment_intent_id', read_only=True)
    payment_status = serializers.CharField(source='status', read_only=True)
    payment_date = serializers.DateTimeField(source='created_at', format='%b %d, %Y %I:%M %p', read_only=True)

    class Meta:
        model = Payment
        fields = ['amount', 'transaction_id', 'payment_status', 'payment_date']

class BookingDetailSerializer(serializers.ModelSerializer):
    customer = CustomerInfoSerializer()
    vehicle = VehicleInfoSerializer(source='car', read_only=True)
    agent = AgentInfoSerializer(source='car.assigned_agent', read_only=True, allow_null=True)

    rental_dates = serializers.SerializerMethodField()

    daily_rate = serializers.ReadOnlyField(source='car.price_per_day')
    number_of_days = serializers.IntegerField(source='total_days', read_only=True)

    # Pricing from Quotation
    insurance_cost = serializers.ReadOnlyField(source='quotation.insurance_cost')
    vat_amount = serializers.ReadOnlyField(source='quotation.vat_amount')
    discount_amount = serializers.ReadOnlyField(source='quotation.discount_amount')
    security_deposit = serializers.ReadOnlyField(source='quotation.security_deposit')
    total_amount = serializers.ReadOnlyField(source='quotation.total_price')

    quotation_notes = serializers.CharField(
        source='quotation.notes_for_customer',
        allow_null=True,
        read_only=True
    )

    payment = PaymentInfoSerializer()

    status_timeline = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'id', 'customer', 'vehicle', 'agent',
            'rental_dates', 'status',
            'daily_rate', 'number_of_days',
            'insurance_cost', 'vat_amount', 'discount_amount',
            'security_deposit', 'total_amount',
            'quotation_notes',
            'payment',
            'status_timeline',
            'created_at'
        ]
    def get_rental_dates(self, obj):
            return {
                "pickup": obj.pickup_date.strftime('%b %d, %Y'),
                "return": obj.return_date.strftime('%b %d, %Y')
            }

    def get_status_timeline(self, obj):
        timeline = []

        timeline.append({
            "event": "Booking Created",
            "date": obj.created_at.strftime('%b %d, %Y %I:%M %p') if obj.created_at else "N/A"
        })

        if hasattr(obj, 'payment') and obj.payment and obj.payment.created_at:
            timeline.append({
                "event": "Payment Confirmed",
                "date": obj.payment.created_at.strftime('%b %d, %Y %I:%M %p')
            })

        if obj.car.assigned_agent:
            timeline.append({
                "event": "Vehicle Assigned",
                "date": obj.updated_at.strftime('%b %d, %Y %I:%M %p')  
            })

        return timeline
    
    
from users.models import Customer   
class CustomerListSerializer(serializers.ModelSerializer):
    customer_id = serializers.CharField(source='id', read_only=True)
    full_name = serializers.CharField(source='name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.CharField(source='phone_number', allow_null=True, read_only=True)
    license_status = serializers.CharField(read_only=True)
    total_bookings = serializers.SerializerMethodField()
    is_vip = serializers.BooleanField(source='vip_status', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'customer_id', 'full_name', 'email', 'phone',
            'license_status', 'total_bookings', 'is_vip'
        ]

    def get_total_bookings(self, obj):
        return RentalRequest.objects.filter(customer=obj.user).count()


class BookingHistorySerializer(serializers.ModelSerializer):
    vehicle = serializers.CharField(source='car.car_name', read_only=True)
    booking_id = serializers.CharField(source='id', read_only=True)
    rental_dates = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)

    class Meta:
        model = RentalRequest
        fields = ['booking_id', 'vehicle', 'rental_dates', 'status']

    def get_rental_dates(self, obj):
        start = obj.pickup_date.strftime('%b %d')
        end = obj.return_date.strftime('%b %d, %Y')
        return f"{start} - {end}"


class CustomerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.CharField(source='phone_number', allow_null=True, read_only=True)
    address = serializers.CharField(default="N/A", read_only=True)
    
    license_status = serializers.CharField(read_only=True)
    license_number = serializers.CharField(read_only=True)
    expiry_date = serializers.DateField(source='license_expiry_date', format='%b %d, %Y', read_only=True)
    
    is_vip = serializers.BooleanField(source='vip_status', read_only=True)
    
    total_bookings = serializers.SerializerMethodField()
    active_bookings = serializers.SerializerMethodField()
    
    booking_history = serializers.SerializerMethodField()
    profile_photo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'full_name', 'profile_photo_url', 'email', 'phone', 'address',
            'license_status', 'license_number', 'expiry_date',
            'is_vip',
            'total_bookings', 'active_bookings',
            'booking_history'
        ]

    def get_total_bookings(self, obj):
        return RentalRequest.objects.filter(customer=obj.user).count()

    def get_active_bookings(self, obj):
        return RentalRequest.objects.filter(
            customer=obj.user,
            status__in=['approved', 'awaiting_payment']
        ).count()

    def get_booking_history(self, obj):
        bookings = RentalRequest.objects.filter(customer=obj.user).order_by('-created_at')[:10]
        return BookingHistorySerializer(bookings, many=True).data

    def get_profile_photo_url(self, obj):
            request = self.context.get('request')
            if obj.profile_photo:
                if request is not None:
                    return request.build_absolute_uri(obj.profile_photo.url)
                from django.conf import settings
                return f"{settings.MEDIA_URL.rstrip('/')}{obj.profile_photo.url}"
            return None    
class VipToggleSerializer(serializers.Serializer):
    is_vip = serializers.BooleanField(required=True)
    
    
class CustomerMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    is_vip = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['full_name', 'is_vip']

    def get_full_name(self, obj):
        try:
            return obj.customer_profile.name or "Unnamed"
        except AttributeError:
            return "No Customer Profile"

    def get_is_vip(self, obj):
        try:
            return obj.customer_profile.vip_status
        except AttributeError:
            return False


class VehicleMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = ['car_name']
        

from agency_agent.models import Quotation        
class QuotationListSerializer(serializers.ModelSerializer):
    customer = CustomerMinimalSerializer(source='rental_request.customer', read_only=True, allow_null=True)
    vehicle = serializers.CharField(source='rental_request.car.car_name', read_only=True)

    vehicle_image_url = serializers.SerializerMethodField(read_only=True)
    
    booking_id = serializers.CharField(source='rental_request.id', read_only=True)
    rental_dates = serializers.SerializerMethodField()

    base_price = serializers.ReadOnlyField()
    extra_charges = serializers.ReadOnlyField(source='extra_services_cost')
    discount = serializers.ReadOnlyField(source='discount_amount')
    total_amount = serializers.ReadOnlyField(source='total_price')

    status = serializers.CharField(read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id', 'booking_id', 'customer', 'vehicle', 'vehicle_image_url',
            'rental_dates', 'base_price', 'extra_charges', 'discount',
            'total_amount', 'status'
        ]

    def get_rental_dates(self, obj):
        start = obj.rental_request.pickup_date.strftime('%b %d')
        end = obj.rental_request.return_date.strftime('%b %d, %Y')
        return f"{start} → {end}"

    def get_vehicle_image_url(self, obj):
        request = self.context.get('request')
        car = obj.rental_request.car
        if car and car.featured_image:
            if request is not None:
                return request.build_absolute_uri(car.featured_image.url)
            from django.conf import settings
            return f"{settings.MEDIA_URL.rstrip('/')}{car.featured_image.url}"
        return None
    

class QuotationDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='rental_request.customer.name', read_only=True)
    vehicle_name = serializers.CharField(source='rental_request.car.car_name', read_only=True)

    base_price = serializers.ReadOnlyField()
    extra_charges = serializers.ReadOnlyField(source='extra_services_cost')
    discount = serializers.ReadOnlyField(source='discount_amount')
    security_deposit = serializers.ReadOnlyField()
    total_amount = serializers.ReadOnlyField(source='total_price')

    notes = serializers.CharField(source='notes_for_customer', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id', 'customer_name', 'vehicle_name',
            'base_price', 'extra_charges', 'discount', 'security_deposit',
            'total_amount', 'notes', 'status'
        ]
        
        
class PaymentListSerializer(serializers.ModelSerializer):
    booking_id = serializers.CharField(source='rental_request.id', read_only=True)
    customer_name = serializers.CharField(source='rental_request.customer.name', read_only=True)

    total_amount = serializers.ReadOnlyField(source='rental_request.total_price')
    paid_amount = serializers.ReadOnlyField(source='amount')
    security_deposit = serializers.ReadOnlyField(source='rental_request.quotation.security_deposit')

    payment_status = serializers.CharField(source='status', read_only=True)
    deposit_status = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'booking_id', 'customer_name', 'total_amount', 'paid_amount',
            'security_deposit', 'payment_status', 'deposit_status'
        ]

    def get_deposit_status(self, obj):
        if obj.rental_request.status == 'completed':
            return 'Refunded'
        elif obj.rental_request.status in ['approved', 'awaiting_payment']:
            return 'Held'
        return 'N/A'


class RecentPaymentActivitySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='rental_request.customer.name', read_only=True)
    amount = serializers.ReadOnlyField()
    date = serializers.DateTimeField(source='created_at', format='%Y-%m-%d', read_only=True)
    action = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['customer_name', 'amount', 'date', 'action']

    def get_action(self, obj):
        if obj.status == 'refunded':
            return f"Deposit refunded - €{obj.amount}"
        return f"Payment received - €{obj.amount}"
    
    
from .models import Agency

class AgencySettingsSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Agency
        fields = [
            # Agency Info
            'name',
            'address_line', 'city', 'state', 'zip_code', 'country',
            'phone', 'email', 'website',
            'logo', 'logo_url',
            
            'email_notifications',
            'booking_alerts',
            'maintenance_alerts',
            'payment_notifications',
            'late_return_alerts',

            'account_type',
            'permission_level',
            'account_status',
            'member_since',
            
            'api_status',
            'last_sync',
            'pricing_base_model',
            'currency',

            'updated_at'
        ]
        read_only_fields = [
            'account_type', 'permission_level', 'account_status', 'member_since',
            'api_status', 'last_sync', 'pricing_base_model', 'currency', 'updated_at'
        ]

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo:
            if request is not None:
                return request.build_absolute_uri(obj.logo.url)
            from django.conf import settings
            return f"{settings.MEDIA_URL.rstrip('/')}{obj.logo.url}"
        return None
    
    
    
class DashboardCheckInOutSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vehicle_name = serializers.CharField(source='car.car_name', read_only=True)
    
    # Use DateTimeField with date-only format
    date = serializers.DateTimeField(source='pickup_date', format='%d %b %Y', read_only=True)
    
    rental_days = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='status', read_only=True)

    class Meta:
        model = RentalRequest
        fields = ['customer_name', 'vehicle_name', 'date', 'rental_days', 'status_display']

    def get_rental_days(self, obj):
        if obj.pickup_date and obj.return_date:
            delta = obj.return_date - obj.pickup_date
            return delta.days if delta.days > 0 else 1
        return 0
    
    
