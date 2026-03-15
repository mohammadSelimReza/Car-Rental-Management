from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from .serializers import AgentCreateSerializer, BookingDetailSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.models import Agency, AgencyAdmin
from . permissions import IsAgencyAdmin

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAgencyAdmin])
def agent_create_view(request):
    if request.method == 'POST':
        try:
            agency_admin = AgencyAdmin.objects.get(user=request.user)
            agency = agency_admin.agency
        except AgencyAdmin.DoesNotExist:
            return Response(
                {"error": "Only agency admins can create agents"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AgentCreateSerializer(
            data=request.data, 
            context={'agency': agency}
        )
        
        if serializer.is_valid():
            agent = serializer.save()
            return Response(
                {
                    "message": "Agent created successfully",
                    "agent": {
                        "id": agent.id,
                        "name": agent.name,
                        "email": agent.user.email,
                        "phone": agent.phone_number
                    }
                }, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
from .serializers import CarCreateSerializer
from . models import Car
from rest_framework.pagination import PageNumberPagination
@api_view(['GET','POST'])
@permission_classes([IsAuthenticated, IsAgencyAdmin])
def add_car_view(request):
    if request.method == 'POST':
        try:
            agency_admin = AgencyAdmin.objects.get(user=request.user)
            agency = agency_admin.agency
        except AgencyAdmin.DoesNotExist:
            return Response(
                {"error": "Only agency admins can add cars"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CarCreateSerializer(
            data=request.data, 
            context={'agency': agency}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Car added successfully",
                    "data": serializer.data
                }, 
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    if request.method == 'GET':
        try:
            agency_admin = AgencyAdmin.objects.get(user=request.user)
            agency = agency_admin.agency
        except AgencyAdmin.DoesNotExist:
            return Response(
                {"error": "Only agency admins can view cars"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        cars = Car.objects.filter(agency=agency).order_by('-created_at')
        
        paginator = PageNumberPagination()
        paginator.page_size = 10
        
        result_page = paginator.paginate_queryset(cars, request)
        serializer = CarCreateSerializer(result_page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAgencyAdmin])
def update_car_view(request, car_id):
    try:
        agency_admin = AgencyAdmin.objects.get(user=request.user)
        agency = agency_admin.agency
    except AgencyAdmin.DoesNotExist:
        return Response(
            {"error": "Only agency admins can update cars"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        car = Car.objects.get(id=car_id, agency=agency)
    except Car.DoesNotExist:
        return Response(
            {"error": "Car not found or not accessible"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'PATCH':
        serializer = CarCreateSerializer(car, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Car updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        car.delete()
        return Response({"message": "Car deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
    
from django.db.models import Q, Sum
from users.models import AgencyAgent
from customers.models import RentalRequest
from .serializers import AgentListSerializer, AgentUpdateSerializer
@api_view(['GET'])
@permission_classes([IsAuthenticated,IsAgencyAdmin])
def agency_agents_list(request):
    agency = request.user.admin_profile.agency

    queryset = AgencyAgent.objects.filter(agency=agency)

    # Search
    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(phone_number__icontains=search)
        )

    total_active_agents = queryset.filter(is_active=True).count()
    total_active_bookings = RentalRequest.objects.filter(
        car__agency=agency,
        car__assigned_agent__in=queryset,
        status__in=['approved', 'awaiting_payment']
    ).count()
    combined_revenue = RentalRequest.objects.filter(
        car__agency=agency,
        car__assigned_agent__in=queryset,
        status__in=['approved', 'completed'],
        quotation__isnull=False
    ).aggregate(
        total=Sum('quotation__total_price')
    )['total'] or 0

    summary = {
        "total_active_agents": total_active_agents,
        "total_active_bookings": total_active_bookings,
        "combined_revenue": f"${combined_revenue:,.0f}"
    }

    serializer = AgentListSerializer(queryset.order_by('name'), many=True)
    
    return Response({
        "summary": summary,
        "agents": serializer.data
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def agency_agent_detail(request, pk):

    try:
        agent = AgencyAgent.objects.get(pk=pk, agency=request.user.admin_profile.agency)
    except AgencyAgent.DoesNotExist:
        return Response({"error": "Agent not found or not in your agency"}, status=404)

    if request.method == 'GET':
        serializer = AgentUpdateSerializer(agent)
        return Response(serializer.data)

    serializer = AgentUpdateSerializer(agent, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from .serializers import BookingListSerializer
def get_agency_from_admin(user):
    if hasattr(user, 'admin_profile') and user.admin_profile.agency:
        return user.admin_profile.agency
    return None
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_booking_list(request):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not an agency admin or no agency"}, status=403)

    queryset = RentalRequest.objects.filter(car__agency=agency).select_related(
        'customer', 'car', 'car__assigned_agent'
    ).order_by('-created_at')

    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            Q(id__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(car__car_name__icontains=search) |
            Q(car__assigned_agent__name__icontains=search)
        )

    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    serializer = BookingListSerializer(queryset, many=True)

    return Response({
        "total_bookings": queryset.count(),
        "bookings": serializer.data
    })
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_booking_detail(request, pk):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not authorized"}, status=403)

    try:
        booking = RentalRequest.objects.select_related(
            'customer', 'car', 'car__assigned_agent', 'quotation'
        ).get(id=pk, car__agency=agency)
    except RentalRequest.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    serializer = BookingDetailSerializer(booking, context={'request': request})
    return Response(serializer.data)



from users.models import Customer
from .serializers import (
    CustomerListSerializer,
    CustomerDetailSerializer,
    VipToggleSerializer
)
from agency_agent.models import Quotation


def get_agency_from_admin(user):
    if hasattr(user, 'admin_profile') and user.admin_profile.agency:
        return user.admin_profile.agency
    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_customer_list(request):
    """
    ?search=john
    """
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not an agency admin or no agency"}, status=403)

    queryset = Customer.objects.filter(
        user__rental_requests__car__agency=agency
    ).distinct().select_related('user')

    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(phone_number__icontains=search)
        )

    serializer = CustomerListSerializer(queryset.order_by('name'), many=True)

    return Response({
        "customers": serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_customer_detail(request, pk):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not authorized"}, status=403)

    customer = Customer.objects.filter(
        pk=pk,
        user__rental_requests__car__agency=agency
    ).select_related('user').first()

    if customer is None:
        return Response({"error": "Customer not found or no bookings in your agency"}, status=404)

    serializer = CustomerDetailSerializer(customer, context={'request': request})
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def agency_customer_vip_toggle(request, pk):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not authorized"}, status=403)

    try:
        customer = Customer.objects.filter(
            pk=pk,
            user__rental_requests__car__agency=agency
        ).select_related('user').first()
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)

    serializer = VipToggleSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    customer.vip_status = serializer.validated_data['is_vip']
    customer.save()

    return Response({
        "message": f"VIP status updated to {'VIP' if customer.vip_status else 'Regular'}",
        "is_vip": customer.vip_status
    })
    

from agency_agent.models import Quotation
from .serializers import QuotationListSerializer, QuotationDetailSerializer
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_quotation_list(request):
    """
    ?search=john
    ?status=sent
    """
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not an agency admin or no agency"}, status=403)

    queryset = Quotation.objects.filter(
        rental_request__car__agency=agency
    ).select_related(
        'rental_request', 'rental_request__customer', 'rental_request__car'
    ).order_by('-created_at')

    # Search
    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            Q(rental_request__customer__name__icontains=search) |
            Q(rental_request__car__car_name__icontains=search) |
            Q(rental_request__id__icontains=search)
        )

    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    serializer = QuotationListSerializer(queryset, many=True)

    return Response({
        "quotations": serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_quotation_detail(request, pk):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not authorized"}, status=403)

    try:
        quotation = Quotation.objects.select_related(
            'rental_request', 'rental_request__customer', 'rental_request__car'
        ).get(id=pk, rental_request__car__agency=agency)
    except Quotation.DoesNotExist:
        return Response({"error": "Quotation not found or not in your agency"}, status=404)

    serializer = QuotationDetailSerializer(quotation, context={'request': request})
    return Response(serializer.data)

from decimal import Decimal
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import timedelta
from customers.models import RentalRequest, Payment
from .serializers import PaymentListSerializer, RecentPaymentActivitySerializer
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_payments_deposits(request):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not an agency admin or no agency"}, status=403)

    bookings = RentalRequest.objects.filter(car__agency=agency)

    total_paid = Payment.objects.filter(
        rental_request__car__agency=agency,
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    pending = bookings.filter(payment_status='pending').aggregate(
        total=Sum('quotation__total_price')
    )['total'] or Decimal('0.00')

    deposits_held = bookings.filter(
        status__in=['approved', 'awaiting_payment']
    ).aggregate(
        total=Sum('quotation__security_deposit')
    )['total'] or Decimal('0.00')

    deposits_refunded = Payment.objects.filter(
        rental_request__car__agency=agency,
        status='refunded'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    summary = {
        "total_paid": total_paid,
        "pending": pending,
        "deposits_held": deposits_held,
        "deposits_refunded": deposits_refunded
    }

    payments = Payment.objects.filter(rental_request__car__agency=agency).select_related(
        'rental_request', 'rental_request__customer'
    ).order_by('-created_at')

    payment_serializer = PaymentListSerializer(payments, many=True)

    recent = Payment.objects.filter(rental_request__car__agency=agency).order_by('-created_at')[:5]
    recent_serializer = RecentPaymentActivitySerializer(recent, many=True)

    return Response({
        "summary": summary,
        "payments": payment_serializer.data,
        "recent_activity": recent_serializer.data
    })
    
    
    
from datetime import datetime, timedelta


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_reports_analytics(request):
    agency = get_agency_from_admin(request.user)
    if not agency:
        return Response({"error": "Not authorized"}, status=403)

    today = timezone.now()
    this_month_start = today.replace(day=1)
    last_month_start = this_month_start - timedelta(days=30)

    months = []
    revenue_data = []
    bookings_data = []

    for i in range(6):
        month_start = today - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)

        month_bookings = RentalRequest.objects.filter(
            car__agency=agency,
            created_at__range=[month_start, month_end]
        )

        month_revenue = month_bookings.aggregate(
            total=Sum('quotation__total_price')
        )['total'] or Decimal('0.00')

        months.append(month_start.strftime('%b'))
        revenue_data.append(float(month_revenue))
        bookings_data.append(month_bookings.count())

    current_month_bookings = RentalRequest.objects.filter(
        car__agency=agency,
        created_at__gte=this_month_start
    ).count()

    current_month_revenue = RentalRequest.objects.filter(
        car__agency=agency,
        created_at__gte=this_month_start
    ).aggregate(
        total=Sum('quotation__total_price')
    )['total'] or Decimal('0.00')

    avg_booking_value = current_month_revenue / current_month_bookings if current_month_bookings else Decimal('0.00')

    total_bookings = RentalRequest.objects.filter(car__agency=agency).count()
    cancelled = RentalRequest.objects.filter(car__agency=agency, status='cancelled').count()
    cancellation_rate = (cancelled / total_bookings * 100) if total_bookings else 0

    data = {
        "monthly_revenue": {
            "current": float(current_month_revenue),
            "change": "+18%" 
        },
        "total_bookings": total_bookings,
        "avg_booking_value": float(avg_booking_value),
        "cancellation_rate": f"{cancellation_rate:.1f}%",
        "revenue_trend": {
            "months": months[::-1],
            "revenue": revenue_data[::-1]
        },
        "bookings_trend": {
            "months": months[::-1],
            "bookings": bookings_data[::-1]
        }
    }

    return Response(data)



from .serializers import AgencySettingsSerializer


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def agency_settings(request):
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile.agency:
        return Response({"error": "Not an agency admin or no agency assigned"}, status=403)

    agency = request.user.admin_profile.agency

    if request.method == 'GET':
        serializer = AgencySettingsSerializer(agency, context={'request': request})
        return Response(serializer.data)

    serializer = AgencySettingsSerializer(
        agency,
        data=request.data,
        partial=True,
        context={'request': request}
    )

    if serializer.is_valid():
        serializer.save(updated_by=request.user)
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



from .serializers import DashboardCheckInOutSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agency_dashboard(request):
    """
    GET /api/agency-admin/dashboard/
    Agency Admin Dashboard - accurate data using correct fields
    """
    # Get agency
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile.agency:
        return Response({"error": "Not an agency admin or no agency"}, status=403)

    agency = request.user.admin_profile.agency

    today = timezone.now().date()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    month_start = today_start.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # ───────────── Summary Cards ─────────────

    total_vehicles = Car.objects.filter(agency=agency).count()
    vehicles_booked = Car.objects.filter(agency=agency, status='booked').count()
    pending_requests = RentalRequest.objects.filter(
        car__agency=agency,
        status__in=['pending', 'quotation_sent', 'awaiting_payment']
    ).count()
    ongoing_rentals = RentalRequest.objects.filter(
        car__agency=agency,
        status='approved',
        pickup_date__lt=today_end,
        return_date__gt=today_start
    ).count()
    reserved_vehicles = Car.objects.filter(agency=agency, status='reserved').count()

    # Monthly Revenue = sum of quotation__total_price for bookings in this month
    monthly_revenue = RentalRequest.objects.filter(
        car__agency=agency,
        created_at__gte=month_start,
        created_at__lt=month_end,
        status__in=['approved', 'completed']
    ).aggregate(total=Sum('quotation__total_price'))['total'] or 0

    # ───────────── Today's Check-ins / Check-outs ─────────────

    todays_checkin = RentalRequest.objects.filter(
        car__agency=agency,
        checkin_completed_at__gte=today_start,
        checkin_completed_at__lt=today_end,
        checkin_completed_at__isnull=False
    ).order_by('checkin_completed_at')

    todays_checkout = RentalRequest.objects.filter(
        car__agency=agency,
        checkout_completed_at__gte=today_start,
        checkout_completed_at__lt=today_end,
        checkout_completed_at__isnull=False
    ).order_by('checkout_completed_at')

    data = {
        "total_vehicles": total_vehicles,
        "vehicles_booked": vehicles_booked,
        "pending_requests": pending_requests,
        "ongoing_rentals": ongoing_rentals,
        "reserved_vehicles": reserved_vehicles,
        "monthly_revenue": f"${monthly_revenue:,.0f}",
        "todays_checkin_checkout": {
            "checkin": DashboardCheckInOutSerializer(todays_checkin[:5], many=True).data,
            "checkout": DashboardCheckInOutSerializer(todays_checkout[:5], many=True).data,
        }
    }

    return Response(data)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vehicle_activity_overview(request):
    agency = request.user.admin_profile.agency

    cars = Car.objects.filter(agency=agency).select_related('agency')

    data = []
    for car in cars:
        bookings = RentalRequest.objects.filter(car=car).order_by('pickup_date')
        periods = []

        for b in bookings:
            periods.append({
                "start": b.pickup_date.isoformat(),
                "end": b.return_date.isoformat(),
                "status": b.status,
                "color": "red" if b.status == 'booked' else "yellow" if b.status == 'maintenance' else "green"
            })

        data.append({
            "license_plate": car.license_plate,
            "description": car.car_name,
            "periods": periods
        })

    return Response({
        "vehicles_count": cars.count(),
        "vehicles": data
    })
    
    
    
