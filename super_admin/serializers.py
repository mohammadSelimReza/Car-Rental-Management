
from rest_framework import serializers
from django.db import transaction
from django.db.models import Count
from users.models import User, Agency, AgencyAdmin
from django.utils import timezone
from users.models import User,Customer
from customers.models import RentalRequest
from users.models import AgencyAdmin, AgencyAgent
from agency_admin.models import Agency
class AgencyCreateSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(required=True, write_only=True)
    admin_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    admin_name = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Agency
        fields = [
            'name', 'logo', 'location', 'phone', 'terms_and_conditions', 
            'privacy_policy', 'admin_name', 'admin_email', 'admin_password'
        ]

    def validate_admin_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An admin with this email already exists.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        admin_name = validated_data.pop('admin_name')
        admin_email = validated_data.pop('admin_email')
        admin_password = validated_data.pop('admin_password')

        agency = Agency.objects.create(**validated_data)

        admin_user = User.objects.create_user(
            username=admin_email,
            email=admin_email,
            password=admin_password,
            role='agency_admin'
        )

        AgencyAdmin.objects.create(
            user=admin_user,
            agency=agency,
            name=admin_name,
            phone_number=agency.phone 
        )
        return agency


from .models import GlobalPricingRule

class GlobalPricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalPricingRule
        fields = [
            'id',
            'default_vat_tax',
            'default_security_deposit',
            'max_discount_limit',
            'vip_discount_default',
            'late_return_penalty',
            'cancellation_policy',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_default_vat_tax(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("VAT/Tax must be between 0 and 100")
        return value
    
    def validate_max_discount_limit(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Maximum discount limit must be between 0 and 100")
        return value
    
    def validate_vip_discount_default(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("VIP discount must be between 0 and 100")
        return value
    
    def validate_default_security_deposit(self, value):
        if value < 0:
            raise serializers.ValidationError("Security deposit cannot be negative")
        return value
    
    def validate_late_return_penalty(self, value):
        if value < 0:
            raise serializers.ValidationError("Late return penalty cannot be negative")
        return value

from users.models import User,AgencyAdmin, AgencyAgent
from .models import GlobalPricingRule
class AgencyMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = ['id', 'name']

class CustomerMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        source='customer_profile.name',
        read_only=True
    )

    class Meta:
        model = User
        fields = ['id', 'full_name']


class AgentMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')

    class Meta:
        model = AgencyAgent
        fields = ['id', 'full_name']

class AgencyAdminSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = AgencyAdmin
        fields = ['full_name']


class AgencyListSerializer(serializers.ModelSerializer):
    admin_name = serializers.SerializerMethodField()
    vehicles_count = serializers.IntegerField(read_only=True)
    status = serializers.BooleanField(source='is_active', read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'location', 'admin_name',
            'vehicles_count', 'status', 'status_display'
        ]

    def get_admin_name(self, obj):
        admin = obj.admins.first()
        if admin:
            if admin.name:
                return admin.name
            user = admin.user
            full_name = user.get_full_name()
            if full_name and full_name.strip():
                return full_name
            return user.email or user.username or "Unnamed Admin"
        return "No Admin Assigned"

    def get_status_display(self, obj):
        return "Active" if obj.is_active else "Disabled"
class AdminListSerializer(serializers.ModelSerializer):
    agency = AgencyMinimalSerializer(read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    status = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source='user.last_login', format='%Y-%m-%d %I:%M %p', read_only=True)

    class Meta:
        model = AgencyAdmin
        fields = [
            'id', 'name', 'agency', 'role', 'status', 'last_login',
        ]

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"


class AgencyAdminSerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source='user.get_full_name', read_only=True)
    admin_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = AgencyAdmin
        fields = ['admin_name', 'admin_email']
from django.db.models import Q,Sum

class AgencyDetailSerializer(serializers.ModelSerializer):
    admin_info = AgencyAdminSerializer(source='admins', many=True, read_only=True)
    total_cars = serializers.IntegerField(read_only=True)
    active_bookings = serializers.IntegerField(read_only=True)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_agents = serializers.IntegerField(read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'location',
            'total_cars', 'active_bookings', 'total_revenue',
            'total_agents', 'commission_rate', 'is_active',
            'status_display', 'admin_info'
        ]

    def get_status_display(self, obj):
        return "Active" if obj.is_active else "Suspended"

    def to_representation(self, instance):
        # Annotate dynamic fields (counts & revenue)
        data = super().to_representation(instance)
        
        # Total cars
        data['total_cars'] = Car.objects.filter(agency=instance).count()
        
        # Active bookings (approved & ongoing)
        today = timezone.now()
        data['active_bookings'] = RentalRequest.objects.filter(
            car__agency=instance,
            status='approved',
            pickup_date__lte=today,
            return_date__gte=today
        ).count()
        
        # Total revenue (example: sum of completed bookings)
        data['total_revenue'] = RentalRequest.objects.filter(
            car__agency=instance,
            status='completed'
        ).aggregate(total=Sum('total_price'))['total'] or 0
        
        # Total agents
        data['total_agents'] = instance.admins.count()
        
        return data
from django.db.models import Q
class AgentListSerializer(serializers.ModelSerializer):
    assigned_agency = AgencyMinimalSerializer(source='agency', read_only=True)
    total_bookings_handled = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = AgencyAgent
        fields = [
            'id', 'name', 'assigned_agency', 'total_bookings_handled', 'status'
        ]

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"

    def get_total_bookings_handled(self, obj):
        return obj.assigned_cars.aggregate(
            total=Count('rental_requests', filter=Q(rental_requests__status__in=['approved', 'completed']))
        )['total'] or 0
        

class CustomerListSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='user.phone_number', default=None, allow_null=True)
    status = serializers.SerializerMethodField()
    joined_date = serializers.SerializerMethodField()
    total_bookings = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'full_name', 'email', 'phone',
            'status', 'joined_date', 'total_bookings','user'
        ]

    def get_user(self, obj):
        return {'id': obj.user.id, 'email': obj.user.email}

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"

    def get_total_bookings(self, obj):
        return RentalRequest.objects.filter(customer=obj.user).count()
    def get_joined_date(self, obj):
        dt = obj.created_at
        return dt.strftime('%m/%d/%Y') if dt else None


class AgencyAdminListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='phone_number', allow_null=True)
    agency = AgencyMinimalSerializer()
    status = serializers.SerializerMethodField()
    joined_date = serializers.SerializerMethodField()

    class Meta:
        model = AgencyAdmin
        fields = [
            'id', 'full_name', 'email', 'phone', 'agency',
            'status', 'joined_date'
        ]

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"
    def get_joined_date(self, obj):
        dt = obj.created_at
        return dt.strftime('%m/%d/%Y') if dt else None


class AgencyAgentListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='phone_number', allow_null=True)
    agency = AgencyMinimalSerializer()
    status = serializers.SerializerMethodField()
    joined_date = serializers.SerializerMethodField()

    class Meta:
        model = AgencyAgent
        fields = [
            'id', 'full_name', 'email', 'phone', 'agency',
            'status', 'joined_date'
        ]

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"
    def get_joined_date(self, obj):
        dt = obj.created_at
        return dt.strftime('%m/%d/%Y') if dt else None


class CustomerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='user.phone_number', allow_null=True)
    address = serializers.SerializerMethodField() 
    status = serializers.SerializerMethodField()
    joined_date = serializers.SerializerMethodField()
    total_bookings = serializers.SerializerMethodField()
    membership_duration_months = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'full_name', 'email', 'phone', 'address',
            'status', 'joined_date', 'total_bookings', 'membership_duration_months'
        ]

    def get_address(self, obj):
        return "N/A" 

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"

    def get_total_bookings(self, obj):
        return RentalRequest.objects.filter(customer=obj.user).count()

    def get_membership_duration_months(self, obj):
        delta = timezone.now() - obj.created_at
        return delta.days // 30
    def get_joined_date(self, obj):
        dt = obj.created_at
        return dt.strftime('%m/%d/%Y') if dt else None


class AgencyAgentDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='phone_number', allow_null=True)
    address = serializers.SerializerMethodField()
    assigned_agency = AgencyMinimalSerializer(source='agency')
    status = serializers.SerializerMethodField()
    joined_date = serializers.SerializerMethodField()

    class Meta:
        model = AgencyAgent
        fields = [
            'id', 'full_name', 'email', 'phone', 'address',
            'assigned_agency', 'status', 'joined_date'
        ]

    def get_address(self, obj):
        return "N/A" 

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"
    
    def get_joined_date(self, obj):
        dt = obj.created_at
        return dt.strftime('%m/%d/%Y') if dt else None
    
    
class AgencyAdminDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='phone_number', allow_null=True)
    address = serializers.SerializerMethodField()
    agency = AgencyMinimalSerializer()
    status = serializers.SerializerMethodField()
    joined_date = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(source='user.last_login', format='%Y-%m-%d %I:%M %p', allow_null=True)

    class Meta:
        model = AgencyAdmin
        fields = [
            'id', 'full_name', 'email', 'phone', 'address',
            'agency', 'status', 'joined_date', 'last_login'
        ]

    def get_address(self, obj):
        return "N/A"

    def get_status(self, obj):
        return "Active" if obj.user.is_active else "Inactive"
    def get_joined_date(self, obj):
        dt = obj.created_at
        return dt.strftime('%m/%d/%Y') if dt else None
    
from agency_admin.models import Car    
    
class BookingOverviewSerializer(serializers.ModelSerializer):
    booking_id = serializers.CharField(source='id', read_only=True)
    agency = AgencyMinimalSerializer(source='car.agency', read_only=True)
    customer = CustomerMinimalSerializer()
    vehicle = serializers.CharField(source='car.car_name', read_only=True)
    rental_period = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    assigned_agent = AgentMinimalSerializer(source='car.assigned_agent', read_only=True)
    amount = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'booking_id', 'agency', 'customer', 'vehicle',
            'rental_period', 'status', 'assigned_agent',
            'amount', 'status_display'
        ]

    def get_rental_period(self, obj):
        start = obj.pickup_date.strftime('%m/%d/%Y')
        end = obj.return_date.strftime('%m/%d/%Y')
        return f"{start}/{end}"

    def get_amount(self, obj):
        if hasattr(obj, 'quotation') and obj.quotation:
            return f"${obj.quotation.total_price:.2f}"
        return f"${obj.total_price:.2f}" if hasattr(obj, 'total_price') else "$0"

    def get_status_display(self, obj):
        status_mapping = {
            'pending': 'Pending',
            'quotation_sent': 'Quotation Sent',
            'awaiting_payment': 'Awaiting Payment',
            'approved': 'Approved',
            'rejected': 'Rejected',
            'cancelled': 'Cancelled',
            'completed': 'Completed',
        }
        return status_mapping.get(obj.status, obj.status.title())



class VehicleOverviewSerializer(serializers.ModelSerializer):
    vehicle = serializers.CharField(source='car_name')
    type = serializers.CharField(source='category')
    license_plate = serializers.CharField(default='N/A')
    agency = AgencyMinimalSerializer()
    mileage = serializers.IntegerField(default=0)
    status = serializers.CharField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Car
        fields = [
            'id', 'vehicle', 'type', 'license_plate',
            'agency', 'mileage', 'status', 'status_display'
        ]
        
    def get_status_display(self, obj):
        status_mapping = {
            'available': 'Available',
            'rented': 'Rented',
            'maintenance': 'Under Maintenance',
            'unavailable': 'Unavailable',
        }
        return status_mapping.get(obj.status, obj.status.title())



from .models import CommissionPayout
class PayoutSummarySerializer(serializers.Serializer):
    total_agency_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_payout = serializers.DecimalField(max_digits=12, decimal_places=2)
    completed_payout = serializers.DecimalField(max_digits=12, decimal_places=2)


class AgencyPayoutListSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name')
    revenue_total = serializers.SerializerMethodField()

    class Meta:
        model = CommissionPayout
        fields = [
            'id', 'agency_name', 'revenue_total', 'commission_rate',
            'commission_amount',
             'status', 'period_start', 'period_end'
        ]

    def get_revenue_total(self, obj):
        return (obj.net_payout or 0) + (obj.commission_amount or 0)



class AgencyPayoutDetailSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name')
    revenue_total = serializers.SerializerMethodField()
    total_bookings = serializers.SerializerMethodField()
    period = serializers.SerializerMethodField()

    class Meta:
        model = CommissionPayout
        fields = [
            'id', 'agency_name', 'period', 'revenue_total',
            'commission_rate', 'total_bookings', 'commission_amount',
            'processing_fee', 'net_payout',
            'status',
            'stripe_payout_id', 'processed_at'
        ]

    def get_revenue_total(self, obj):
        return (obj.net_payout or 0) + (obj.commission_amount or 0)

    def get_total_bookings(self, obj):
        return RentalRequest.objects.filter(
            car__agency=obj.agency,
            pickup_date__range=[obj.period_start, obj.period_end],
            status__in=['approved', 'completed']
        ).count()


    def get_period(self, obj):
        return f"{obj.period_start.strftime('%B %Y')}"

from .models import PlatformSettings


class PlatformSettingsSerializer(serializers.ModelSerializer):
    platform_logo_url = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = PlatformSettings
        fields = '__all__'
        read_only_fields = ['platform_logo_url','updated_at', 'updated_by']
    def get_platform_logo_url(self, obj):
        request = self.context.get('request')
        if obj.platform_logo and hasattr(obj.platform_logo, 'url'):
            return request.build_absolute_uri(obj.platform_logo.url)
        return None
    
    
class DashboardCheckInOutSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    vehicle_name = serializers.CharField(source='car.car_name', read_only=True)

    date = serializers.DateTimeField(
        source='pickup_date',
        format='%d %b %Y',
        read_only=True
    )

    rental_days = serializers.SerializerMethodField()

    time = serializers.DateTimeField(
        source='pickup_date',
        format='%I:%M %p',
        read_only=True
    )

    status_display = serializers.CharField(source='status', read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'customer_name',
            'vehicle_name',
            'date',
            'rental_days',
            'time',
            'status_display'
        ]

    def get_rental_days(self, obj):
        if obj.pickup_date and obj.return_date:
            delta = obj.return_date - obj.pickup_date
            return max(delta.days, 1)
        return 0
class DashboardBarChartSerializer(serializers.Serializer):
    day = serializers.CharField()
    checkin = serializers.IntegerField()
    checkout = serializers.IntegerField()
    
    
    
class CustomerListSerializerAll(serializers.ModelSerializer):
    email = serializers.CharField(source='user.email', read_only=True)
    total_bookings = serializers.IntegerField(read_only=True)
    total_spending = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    license_status_display = serializers.CharField(source='license_status', read_only=True)
    vip_status = serializers.BooleanField(read_only=True)
    is_flagged = serializers.BooleanField(read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'email',
            'total_bookings', 'total_spending',
            'vip_status', 'license_status_display',
            'is_flagged', 'is_active'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        data['total_bookings'] = RentalRequest.objects.filter(
            customer=instance.user
        ).count()

        data['total_spending'] = RentalRequest.objects.filter(
            customer=instance.user,
            status='completed'
        ).aggregate(total=Sum('quotation__total_price'))['total'] or 0
        
        return data
    def get_is_active(self, obj):
        return obj.user.is_active
    
class VehicleOverviewSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    status_display = serializers.CharField(source='status', read_only=True)

    class Meta:
        model = Car
        fields = [
            'id', 'car_name', 'license_plate',
            'agency_name', 'mileage', 'status', 'status_display'
        ]

class BookingOverviewSerializer(serializers.ModelSerializer):
    booking_id = serializers.CharField(read_only=True)
    agency_name = serializers.CharField(source='car.agency.name', read_only=True, allow_null=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    vehicle_name = serializers.CharField(source='car.car_name', read_only=True)
    agent_name = serializers.CharField(source='car.assigned_agent.name', read_only=True, allow_null=True)
    rental_period = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    status_display = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'booking_id',
            'agency_name',
            'customer_name',
            'vehicle_name',
            'rental_period',
            'status',
            'status_display',
            'agent_name',
            'amount'
        ]

    def get_rental_period(self, obj):
        if obj.pickup_date and obj.return_date:
            pickup = obj.pickup_date.strftime('%m/%d/%Y')
            return_date = obj.return_date.strftime('%m/%d/%Y')
            return f"{pickup} - {return_date}"
        return "N/A"

    def get_amount(self, obj):
        # Pull from quotation.total_price
        if obj.quotation:
            return f"${obj.quotation.total_price:,.2f}"
        return "$0.00"

    def get_status_display(self, obj):
        status_map = {
            'approved': 'Active',
            'completed': 'Completed',
            'pending': 'Pending',
            'upcoming': 'Upcoming',
            'cancelled': 'Cancelled',
        }
        return status_map.get(obj.status, obj.status.capitalize())