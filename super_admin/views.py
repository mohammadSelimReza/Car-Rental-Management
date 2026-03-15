from django.db import models

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count
from django.shortcuts import get_object_or_404
from users.models import User, AgencyAdmin, AgencyAgent
from .serializers import AdminListSerializer, AgentListSerializer

from users.models import Agency
from .serializers import AgencyCreateSerializer
from .models import GlobalPricingRule
from .serializers import GlobalPricingRuleSerializer
from .permissions import IsSuperAdmin
from users.models import Customer
from .serializers import (
    CustomerListSerializer, AgencyAdminListSerializer, AgencyAgentListSerializer,
    CustomerDetailSerializer, AgencyAgentDetailSerializer,AgencyAdminDetailSerializer
)
from .models import CommissionPayout
from decimal import Decimal
from django.db.models import Sum, Count
import stripe
from django.conf import settings
from django.utils import timezone
from .serializers import (
    PayoutSummarySerializer,
    AgencyPayoutListSerializer,
    AgencyPayoutDetailSerializer
)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def agency_create_view(request):
    if request.method == 'POST':
        serializer = AgencyCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            agency = serializer.save()
            return Response(
                {
                    "message": "Agency created successfully",
                    "agency": {
                        "id": agency.id,
                        "name": agency.name,
                        "location": agency.location,
                        "phone": agency.phone,
                        "logo": agency.logo.url if agency.logo else None,
                        "status": agency.status,
                        "created_at": agency.created_at
                    }
                }, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
from .serializers import AgencyListSerializer
from django.db.models import Count, Q

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def super_admin_agency_list(request):

    agencies = Agency.objects.annotate(
        vehicles_count=Count('cars')
    ).order_by('-vehicles_count')

    search = request.query_params.get('search')
    if search:
        agencies = agencies.filter(
            Q(name__icontains=search) |
            Q(location__icontains=search) |
            Q(primary_admin__user__first_name__icontains=search) |
            Q(primary_admin__user__last_name__icontains=search)
        )

    serializer = AgencyListSerializer(agencies, many=True, context={'request': request})

    return Response({
        "agencies": serializer.data,
        "total_agencies": agencies.count()
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def toggle_agency_status(request, agency_id):

    agency = get_object_or_404(Agency, id=agency_id)

    agency.is_active = not agency.is_active
    agency.save()

    return Response({
        "id": agency.id,
        "name": agency.name,
        "status": agency.is_active
    })


from .serializers import AgencyDetailSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def agency_detail(request, agency_id):
    agency = get_object_or_404(Agency, id=agency_id)

    # Calculate dynamic fields
    total_cars = Car.objects.filter(agency=agency).count()

    today = timezone.now()
    active_bookings = RentalRequest.objects.filter(
        car__agency=agency,
        status='approved',
        pickup_date__lte=today,
        return_date__gte=today
    ).count()

    total_revenue = RentalRequest.objects.filter(
        car__agency=agency,
        status='completed'
    ).aggregate(total=Sum('quotation__total_price'))['total'] or 0

    total_agents = AgencyAdmin.objects.filter(agency=agency).count()

    data = {
        "id": agency.id,
        "name": agency.name,
        "location": agency.location or "Not specified",
        "total_cars": total_cars,
        "active_bookings": active_bookings,
        "total_revenue": f"${total_revenue:,.2f}",
        "total_agents": total_agents,
        "commission_rate": agency.commission_rate,
        "is_active": agency.is_active,
        "status_display": "Active" if agency.is_active else "Suspended",
        # Admin info (first admin as example)
        "admin_info": [
            {
                "admin_name": admin.user.get_full_name() or admin.user.username,
                "admin_email": admin.user.email
            }
            for admin in agency.admins.all()[:1]  # show first admin only
        ]
    }

    return Response(data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def update_agency_commission(request, agency_id):
    agency = get_object_or_404(Agency, id=agency_id)

    commission_rate = request.data.get('commission_rate')
    if commission_rate is None:
        return Response({"error": "commission_rate is required"}, status=400)

    try:
        commission_rate = float(commission_rate)
        if not 0 <= commission_rate <= 100:
            return Response({"error": "Commission rate must be between 0 and 100"}, status=400)
    except (ValueError, TypeError):
        return Response({"error": "Invalid commission rate format"}, status=400)

    agency.commission_rate = commission_rate
    agency.save()

    return Response({
        "id": agency.id,
        "name": agency.name,
        "commission_rate": agency.commission_rate
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def toggle_agency_suspension(request, agency_id):
    

    agency = get_object_or_404(Agency, id=agency_id)

    suspend = request.data.get('suspend', True)  # default suspend
    reason = request.data.get('reason', '')

    if suspend:
        agency.is_active = False
        agency.suspension_reason = reason
        agency.suspended_at = timezone.now()
    else:
        agency.is_active = True
        agency.suspension_reason = None
        agency.suspended_at = None

    agency.save()

    return Response({
        "id": agency.id,
        "name": agency.name,
        "is_active": agency.is_active,
        "status": "Active" if agency.is_active else "Suspended",
        "suspension_reason": agency.suspension_reason
    })
@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def global_pricing_rules_view(request):
    rule = GlobalPricingRule.objects.first()
    
    if request.method == 'GET':
        if rule:
            serializer = GlobalPricingRuleSerializer(rule)
            return Response(serializer.data)
        else:
            return Response({
                "default_vat_tax": 0.0,
                "default_security_deposit": 0.0,
                "max_discount_limit": 0.0,
                "vip_discount_default": 0.0,
                "late_return_penalty": 0.0,
                "cancellation_policy": ""
            })
    
    elif request.method == 'POST':
        if rule:
            return Response(
                {"error": "Global pricing rules already exist. Use PUT to update."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = GlobalPricingRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(
                {
                    "message": "Global pricing rules created successfully",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'PATCH':
        if not rule:
            serializer = GlobalPricingRuleSerializer(data=request.data,partial=True)
            if serializer.is_valid():
                serializer.save(updated_by=request.user)
                return Response(
                    {
                        "message": "Global pricing rules created successfully",
                        "data": serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
        else:
            serializer = GlobalPricingRuleSerializer(rule, data=request.data)
            if serializer.is_valid():
                serializer.save(updated_by=request.user)
                return Response(
                    {
                        "message": "Global pricing rules updated successfully",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def super_admin_admins_agents_list(request):
    tab_type = request.query_params.get('type', 'agents').lower()

    total_admins = AgencyAdmin.objects.count()
    total_agents = AgencyAgent.objects.count()
    active_users = User.objects.filter(
        is_active=True,
        role__in=['agency_admin', 'agency_agent']
    ).count()

    summary = {
        "total_admins": total_admins,
        "total_agents": total_agents,
        "active_users": active_users,
    }

    if tab_type == 'admins':
        queryset = AgencyAdmin.objects.select_related('user', 'agency').order_by('name')
        serializer = AdminListSerializer(queryset, many=True)
        return Response({
            "tab": "admins",
            "items": serializer.data,
            "summary": summary
        })

    else:
        queryset = AgencyAgent.objects.select_related('agency').order_by('name')
        serializer = AgentListSerializer(queryset, many=True)
        return Response({
            "tab": "agents",
            "items": serializer.data,
            "summary": summary
        })
        
from rest_framework import serializers       
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def toggle_admin_active(request, pk):
    admin = get_object_or_404(AgencyAdmin, pk=pk)
    
    serializer = serializers.Serializer(data=request.data)
    serializer.fields['is_active'] = serializers.BooleanField(required=True)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    new_status = serializer.validated_data['is_active']

    admin.user.is_active = new_status
    admin.user.save()

    updated_admin = AdminListSerializer(admin, context={'request': request})
    return Response({
        "message": f"Agency Admin {'activated' if new_status else 'deactivated'} successfully.",
        "admin": updated_admin.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def toggle_agent_active(request, pk):
    agent = get_object_or_404(AgencyAgent, pk=pk)
    
    serializer = serializers.Serializer(data=request.data)
    serializer.fields['is_active'] = serializers.BooleanField(required=True)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    new_status = serializer.validated_data['is_active']

    agent.user.is_active = new_status
    agent.user.save()

    updated_agent = AgentListSerializer(agent, context={'request': request})
    return Response({
        "message": f"Agency Agent {'activated' if new_status else 'deactivated'} successfully.",
        "agent": updated_agent.data
    })
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def user_management_list(request):
    tab = request.query_params.get('tab', 'agents').lower()

    total_customers = Customer.objects.count()
    total_admins   = AgencyAdmin.objects.count()
    total_agents   = AgencyAgent.objects.count()

    summary = {
        "customers": total_customers,
        "agency_admins": total_admins,
        "agents": total_agents,
    }

    if tab == 'customers':
        qs = Customer.objects.select_related('user').order_by('-created_at')
        serializer = CustomerListSerializerAll(qs, many=True)
        return Response({"tab": "customers", "items": serializer.data, "counts": summary})

    elif tab == 'agency_admins':
        qs = AgencyAdmin.objects.select_related('user', 'agency').order_by('-created_at')
        serializer = AgencyAdminListSerializer(qs, many=True)
        return Response({"tab": "agency_admins", "items": serializer.data, "counts": summary})

    else:
        qs = AgencyAgent.objects.select_related('agency').order_by('-created_at')
        serializer = AgencyAgentListSerializer(qs, many=True)
        return Response({"tab": "agents", "items": serializer.data, "counts": summary})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def user_detail(request, user_type, pk):

    if user_type == 'customer':
        profile = get_object_or_404(Customer, pk=pk)
        serializer = CustomerDetailSerializer(profile)
        role_display = "Customer"

    elif user_type == 'agency_admin':
        profile = get_object_or_404(AgencyAdmin, pk=pk)
        serializer = AgencyAdminDetailSerializer(profile)  
        role_display = "Agency Admin"

    elif user_type == 'agent':
        profile = get_object_or_404(AgencyAgent, pk=pk)
        serializer = AgencyAgentDetailSerializer(profile)
        role_display = "Agent"

    else:
        return Response({"error": "Invalid user type"}, status=400)

    return Response({
        "role_display": role_display,
        "data": serializer.data
    })

from agency_agent.models import RentalRequest
from django.db.models import Sum, Max, OuterRef, Subquery

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def payments_commission_overview(request):
    completed = CommissionPayout.objects.filter(
        status='completed'
    ).aggregate(
        total=Sum('net_payout')
    )['total'] or Decimal('0.00')

    pending = CommissionPayout.objects.filter(
        status='pending'
    ).aggregate(
        total=Sum('net_payout')
    )['total'] or Decimal('0.00')

    total_commission = CommissionPayout.objects.aggregate(
        total=Sum('commission_amount')
    )['total'] or Decimal('0.00')

    total_earnings = RentalRequest.objects.filter(
        status__in=['approved', 'completed']
    ).aggregate(
        total=Sum('quotation__total_price')
    )['total'] or Decimal('0.00')

    summary = {
        'total_agency_earnings': total_earnings,
        'platform_commission': total_commission,
        'pending_payout': pending,
        'completed_payout': completed,
    }

    latest_payout_subquery = CommissionPayout.objects.filter(
        agency=OuterRef('agency'),
        status__in=['pending', 'completed']
    ).order_by('-period_end')

    latest_payouts = CommissionPayout.objects.filter(
        id=Subquery(latest_payout_subquery.values('id')[:1])
    )

    list_serializer = AgencyPayoutListSerializer(latest_payouts, many=True)

    revenue_insights = {
        'total_commission': total_commission,
        'agency_count': CommissionPayout.objects.values('agency').distinct().count(),
        'avg_rate': (total_commission / total_earnings * 100) if total_earnings else 0
    }

    return Response({
        'summary': summary,
        'agencies': list_serializer.data,
        'revenue_insights': revenue_insights
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def agency_payout_detail(request, payout_id):
    payout = get_object_or_404(CommissionPayout, id=payout_id)
    serializer = AgencyPayoutDetailSerializer(payout)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def create_account_and_payout(request, payout_id):
    payout = get_object_or_404(CommissionPayout, id=payout_id, status='pending')
    agency = payout.agency

    try:
        if not agency.stripe_connect_account_id:
            account = stripe.Account.create(
                type="express",
                country="US",
                email=request.user.email,
                capabilities={
                    "transfers": {"requested": True}
                },
            )
            agency.stripe_connect_account_id = account.id
            agency.stripe_account_status = "created"
            agency.save()

            account_link = stripe.AccountLink.create(
                account=agency.stripe_connect_account_id,
                refresh_url=settings.FRONTEND_URL,
                return_url=settings.FRONTEND_URL,
                type="account_onboarding",
            )

            return Response({
                "message": "Stripe account created. Complete onboarding first.",
                "onboarding_url": account_link.url
            })

        if not agency.stripe_onboarding_completed:
            account_link = stripe.AccountLink.create(
                account=agency.stripe_connect_account_id,
                refresh_url=settings.FRONTEND_URL,
                return_url=settings.FRONTEND_URL,
                type="account_onboarding",
            )
            return Response({
                "message": "Complete Stripe onboarding first.",
                "onboarding_url": account_link.url
            })

        transfer = stripe.Transfer.create(
            amount=int(payout.net_payout * 100),
            currency="usd",
            destination=agency.stripe_connect_account_id,
            metadata={
                "payout_id": payout.id,
                "agency_id": agency.id
            }
        )

        payout.stripe_transfer_id = transfer.id
        payout.status = "processing"
        payout.processed_at = timezone.now()
        payout.save()

        transfer_url = f"https://dashboard.stripe.com/transfers/{transfer.id}"

        return Response({
            "message": "Payout processing initiated",
            "transfer_id": transfer.id,
            "transfer_url": transfer_url
        })

    except stripe.error.StripeError as e:
        return Response({"error": e.user_message or str(e)}, status=400)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
@csrf_exempt
@api_view(["POST"])
def stripe_webhook_for_payout(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET_FOR_PAYOUT

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "transfer.created":
        payout_id = data["metadata"].get("payout_id")

        payout = CommissionPayout.objects.filter(id=payout_id).first()
        if payout:
            payout.status = "processing"
            payout.stripe_transfer_id = data["id"]
            payout.save()

    elif event_type == "transfer.failed":
        payout_id = data["metadata"].get("payout_id")

        payout = CommissionPayout.objects.filter(id=payout_id).first()
        if payout:
            payout.status = "failed"
            payout.save()

    elif event_type == "payout.paid":
        transfer_id = data.get("source_transfer")

        payout = CommissionPayout.objects.filter(
            stripe_transfer_id=transfer_id
        ).first()

        if payout:
            payout.status = "completed"
            payout.stripe_payout_id = data["id"]
            payout.save()

    return HttpResponse(status=200)    
    
from .models import PlatformSettings
from .serializers import PlatformSettingsSerializer


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def platform_settings(request):
    settings_obj = PlatformSettings.get_settings()

    if request.method == 'GET':
        serializer = PlatformSettingsSerializer(
            settings_obj,
            context={'request': request}
        )
        return Response(serializer.data)

    # Update (PUT/PATCH)
    serializer = PlatformSettingsSerializer(
        settings_obj,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request}
    )
    if serializer.is_valid():
        instance = serializer.save(updated_by=request.user)
        return Response(
            PlatformSettingsSerializer(
                instance,
                context={'request': request}
            ).data
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def reset_platform_settings_to_defaults(request):
    settings_obj = PlatformSettings.get_settings()

    for field in settings_obj._meta.fields:
        if field.name in ['id', 'updated_at', 'updated_by']:
            continue

        # only reset if default exists
        if field.default is not models.NOT_PROVIDED:
            default_value = field.default
            if callable(default_value):
                default_value = default_value()

            setattr(settings_obj, field.name, default_value)

    settings_obj.updated_by = request.user
    settings_obj.save()

    serializer = PlatformSettingsSerializer(
        settings_obj,
        context={'request': request}
    )

    return Response({
        "message": "All settings have been reset to default values.",
        "settings": serializer.data
    }, status=status.HTTP_200_OK)
    
    

from .serializers import DashboardCheckInOutSerializer, DashboardBarChartSerializer

from django.utils import timezone
from datetime import timedelta, datetime, time

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def super_admin_dashboard(request):

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Month range
    month_start = today_start.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # ───────────── Summary Cards ─────────────

    total_agencies = Agency.objects.count()
    total_vehicles = Car.objects.count()

    active_rentals = RentalRequest.objects.filter(
        status="approved",
        pickup_date__lt=today_end,
        return_date__gt=today_start,
    ).count()

    total_bookings = RentalRequest.objects.count()

    # ───────────── Today's Check-ins / Check-outs ─────────────

    todays_checkin = RentalRequest.objects.filter(
        checkin_completed_at__isnull=False,
        checkin_completed_at__gte=today_start,
        checkin_completed_at__lt=today_end,
    ).order_by("checkin_completed_at")

    todays_checkout = RentalRequest.objects.filter(
        checkout_completed_at__isnull=False,
        checkout_completed_at__gte=today_start,
        checkout_completed_at__lt=today_end,
    ).order_by("checkout_completed_at")

    # ───────────── Chart Data ─────────────

    chart_data = []

    current_date = month_start.date()
    end_date = month_end.date()

    tz = timezone.get_current_timezone()

    while current_date <= end_date:

        day_start = datetime.combine(current_date, time.min).replace(tzinfo=tz)
        day_end = datetime.combine(current_date, time.max).replace(tzinfo=tz)

        checkin_count = RentalRequest.objects.filter(
            checkin_completed_at__isnull=False,
            checkin_completed_at__gte=day_start,
            checkin_completed_at__lt=day_end,
        ).count()

        checkout_count = RentalRequest.objects.filter(
            checkout_completed_at__isnull=False,
            checkout_completed_at__gte=day_start,
            checkout_completed_at__lt=day_end,
        ).count()

        chart_data.append({
            "day": current_date.strftime("%a"),
            "checkin": checkin_count,
            "checkout": checkout_count,
        })

        current_date += timedelta(days=1)

    response = {
        "total_agencies": total_agencies,
        "total_vehicles": total_vehicles,
        "active_rentals": active_rentals,
        "total_bookings": total_bookings,
        "todays_checkin_checkout": {
            "checkin": DashboardCheckInOutSerializer(
                todays_checkin[:5],
                many=True
            ).data,
            "checkout": DashboardCheckInOutSerializer(
                todays_checkout[:5],
                many=True
            ).data,
        },
        "checkin_vs_checkout_chart": {
            "data": chart_data,
            "period": "Daily"
        }
    }

    return Response(response)



from .serializers import CustomerListSerializerAll


@api_view(['GET'])
@permission_classes([IsAuthenticated,IsSuperAdmin])
def super_admin_customers_list(request):
    customers = Customer.objects.select_related('user').order_by('-created_at')

    search = request.query_params.get('search')
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(user__email__icontains=search)
        )

    vip_only = request.query_params.get('vip_only') == 'true'
    if vip_only:
        customers = customers.filter(vip_status=True)

    serializer = CustomerListSerializerAll(customers, many=True, context={'request': request})

    return Response({
        "customers": serializer.data,
        "total_customers": customers.count()
    })

@api_view(['PATCH'])
@permission_classes([IsAuthenticated,IsSuperAdmin])
def toggle_customer_suspension(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    user = customer.user

    suspend = request.data.get('suspend', True)
    reason = request.data.get('reason', '').strip() 
    if suspend:
        user.is_active = False
        action = "Suspended"
    else:
        user.is_active = True
        action = "Reactivated"

    user.save(update_fields=['is_active'])

    return Response({
        "id": customer.id,
        "name": customer.name,
        "email": user.email,
        "user_id": user.id,
        "is_active": user.is_active,
        "status": action,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated,IsSuperAdmin])
def toggle_customer_vip(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    make_vip = request.data.get('make_vip', True)

    customer.vip_status = make_vip
    customer.save()

    return Response({
        "id": customer.id,
        "name": customer.name,
        "vip_status": customer.vip_status
    })
    
    
@api_view(['PATCH'])
@permission_classes([IsAuthenticated,IsSuperAdmin])
def toggle_customer_flag(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    flag = request.data.get('flag', True)

    customer.is_flagged = flag
    customer.save()

    return Response({
        "id": customer.id,
        "name": customer.name,
        "is_flagged": customer.is_flagged
    })
    
    
from .serializers import VehicleOverviewSerializer, BookingOverviewSerializer

from agency_admin.models import Car
@api_view(['GET'])
@permission_classes([IsAuthenticated,IsSuperAdmin])
def super_admin_operation_overview(request):

    tab = request.query_params.get('tab', 'vehicles')
    search = request.query_params.get('search', '').strip()

    if tab == 'vehicles':
        vehicles = Car.objects.select_related('agency').order_by('car_name')

        if search:
            vehicles = vehicles.filter(
                Q(car_name__icontains=search) |
                Q(license_plate__icontains=search) |
                Q(agency__name__icontains=search)
            )

        serializer = VehicleOverviewSerializer(vehicles, many=True)
        return Response({
            "tab": "vehicles",
            "vehicles": serializer.data,
            "total_vehicles": vehicles.count()
        })

    elif tab == 'bookings':
        bookings = RentalRequest.objects.select_related(
            'car', 'customer', 'quotation', 'payment'
        ).prefetch_related(
            'car__agency', 
            'car__assigned_agent'
        ).order_by('-pickup_date')

        if search:
            bookings = bookings.filter(
                Q(booking_id__icontains=search) |
                Q(customer__name__icontains=search) |
                Q(car__car_name__icontains=search) |
                Q(car__agency__name__icontains=search)
            )

        serializer = BookingOverviewSerializer(bookings, many=True)
        return Response({
            "tab": "bookings",
            "bookings": serializer.data,
            "total_bookings": bookings.count()
        })

    return Response({"error": "Invalid tab"}, status=400)