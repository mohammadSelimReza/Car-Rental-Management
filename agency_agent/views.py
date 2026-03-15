from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from customers.models import RentalRequest
from super_admin.models import GlobalPricingRule
from .models import Quotation
from .serializers import CheckOutFullSerializer, CreateQuotationSerializer, AgentRentalRequestCardSerializer


@api_view(['POST'])
def create_quotation(request, request_id):
    rental_request = RentalRequest.objects.get(id=request_id, status='pending')
    
    serializer = CreateQuotationSerializer(data=request.data, context={'rental_request': rental_request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    data = serializer.validated_data

    pricing_rules = GlobalPricingRule.objects.first()
    if not pricing_rules:
        return Response({"error": "Global pricing rules not configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    total_days = rental_request.total_days
    base_price = total_days * rental_request.car.price_per_day
    
    extra_services_cost = 0
    for service in rental_request.extra_services.all():
        extra_services_cost += total_days * service.price_per_day
        
    subtotal = base_price + extra_services_cost + data.get('insurance_cost', 0)
    
    vat_percentage = pricing_rules.default_vat_tax
    vat_amount = subtotal * (vat_percentage / 100)
    
    discount = data.get('discount_amount', 0)
    
    security_deposit = data.get('security_deposit', pricing_rules.default_security_deposit)
    
    total_price = (subtotal + vat_amount) - discount
    quotation = Quotation.objects.create(
        rental_request=rental_request,
        created_by=request.user.agent_profile,
        base_price=base_price,
        insurance_cost=data.get('insurance_cost', 0),
        extra_services_cost=extra_services_cost,
        subtotal=subtotal,
        vat_percentage=vat_percentage,
        vat_amount=vat_amount,
        discount_amount=discount,
        security_deposit=security_deposit,
        total_price=total_price,
        notes_for_customer=data.get('notes_for_customer', ''),
        status='sent',
        sent_at=timezone.now()
    )
    
    rental_request.status = 'quotation_sent'
    rental_request.save()
    
    return Response({"message": "Quotation sent successfully."}, status=status.HTTP_201_CREATED)


from django.db.models import Count, Q
from .serializers import (
    AgentRentalRequestCardSerializer, 
    AgentRentalRequestDetailSerializer,
    RejectRequestSerializer
)

def get_agent_profile(user):
    # Use a try-except block to handle cases where a user might not have a profile
    try:
        return user.agent_profile
    except AttributeError:
        return None

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_rental_request_list(request):
    agent_profile = get_agent_profile(request.user)
    if not agent_profile:
        return Response({"error": "User is not a configured agency agent."}, status=status.HTTP_403_FORBIDDEN)

    base_queryset = RentalRequest.objects.filter(car__assigned_agent=agent_profile)

    status_counts = base_queryset.aggregate(
        pending=Count('id', filter=Q(status__in=['pending', 'quotation_sent'])),
        active=Count('id', filter=Q(status__in=['approved', 'awaiting_payment'])),
        rejected=Count('id', filter=Q(status__in=['rejected', 'cancelled']))
    )

    status_filter = request.query_params.get('status')
    if status_filter == 'pending':
        filtered_queryset = base_queryset.filter(status__in=['pending', 'quotation_sent'])
    elif status_filter == 'active':
        filtered_queryset = base_queryset.filter(status__in=['approved', 'awaiting_payment'])
    elif status_filter == 'rejected':
        filtered_queryset = base_queryset.filter(status__in=['rejected', 'cancelled'])
    else:
        filtered_queryset = base_queryset.filter(status__in=['pending', 'quotation_sent'])

    serializer = AgentRentalRequestCardSerializer(filtered_queryset.order_by('-created_at'), many=True, context={'request': request})
    
    response_data = {
        "counts": status_counts,
        "requests": serializer.data
    }
    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_rental_request_detail(request, pk):
    agent_profile = get_agent_profile(request.user)
    if not agent_profile:
        return Response({"error": "User is not a configured agency agent."}, status=status.HTTP_403_FORBIDDEN)
        
    try:
        rental_request = RentalRequest.objects.get(pk=pk, car__assigned_agent=agent_profile)
    except RentalRequest.DoesNotExist:
        return Response({"error": "Rental request not found or not assigned to you."}, status=status.HTTP_404_NOT_FOUND)

    serializer = AgentRentalRequestDetailSerializer(rental_request)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_rental_request(request, pk):
    agent_profile = get_agent_profile(request.user)
    if not agent_profile:
        return Response({"error": "User is not a configured agency agent."}, status=status.HTTP_403_FORBIDDEN)

    try:
        rental_request = RentalRequest.objects.get(pk=pk, car__assigned_agent=agent_profile, status='pending')
    except RentalRequest.DoesNotExist:
        return Response({"error": "Request not found, not assigned to you, or cannot be rejected at this time."}, status=status.HTTP_404_NOT_FOUND)
        
    serializer = RejectRequestSerializer(data=request.data)
    if serializer.is_valid():
        rental_request.status = 'rejected'
        rental_request.rejection_reason = serializer.validated_data['rejection_reason']
        rental_request.save()
        return Response({"message": "Booking has been successfully rejected."}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



from .serializers import CheckinFullSerializer,BookingSummarySerializer
from django.shortcuts import get_object_or_404

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_checkin_bookings(request):
    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agent"}, status=403)

    agent = request.user.agent_profile

    queryset = RentalRequest.objects.filter(car__assigned_agent=agent)

    tab = request.query_params.get('tab', 'all')

    if tab == 'checkin':
        queryset = queryset.filter(checkin_completed=False)

    elif tab == 'checkout':
        queryset = queryset.filter(checkin_completed=True, status='approved')

    serializer = BookingSummarySerializer(
        queryset.order_by('pickup_date'),
        many=True
    )

    return Response({"bookings": serializer.data})



@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def agent_checkin_detail(request, pk):

    print("FILES:", request.FILES)
    print("DATA:", request.data)

    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agent"}, status=403)

    agent = request.user.agent_profile

    booking = get_object_or_404(
        RentalRequest,
        pk=pk,
        car__assigned_agent=agent,
        checkin_completed=False
    )

    if request.method == 'GET':
        serializer = CheckinFullSerializer(
            booking,
            context={'request': request}
        )
        return Response(serializer.data)

    serializer = CheckinFullSerializer(
        booking,
        data=request.data,
        partial=True,
        context={'request': request}
    )

    if serializer.is_valid():
        serializer.save()

        if request.data.get('advance_step'):

            current = booking.checkin_current_step

            if current < 6:
                booking.checkin_current_step += 1

            if booking.checkin_current_step == 6 and all([
                booking.checkin_starting_km is not None,
                booking.checkin_fuel_level,
                booking.checkin_car_condition,
                booking.document_verified
            ]):
                booking.checkin_completed = True
                booking.checkin_completed_at = timezone.now()
                booking.checkin_completed_by = agent

            booking.save()

        return Response(
            CheckinFullSerializer(
                booking,
                context={'request': request}
            ).data
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def agent_checkout_detail(request, pk):

    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agent"}, status=403)

    agent = request.user.agent_profile
    
    booking = get_object_or_404(
        RentalRequest,
        pk=pk,
        car__assigned_agent=agent,
        checkin_completed=True,
        checkout_status__in=['in_progress', 'pending']
    )
    print(booking.checkout_status)
    if request.method == "GET":
        serializer = CheckOutFullSerializer(
            booking,
            context={"request": request}
        )
        return Response(serializer.data)

    serializer = CheckOutFullSerializer(
        booking,
        data=request.data,
        partial=True,
        context={"request": request}
    )

    if serializer.is_valid():
        serializer.save()

        if request.data.get("advance_step"):

            current = booking.checkout_current_step

            if current < 3:
                booking.checkout_current_step += 1
                booking.checkout_status = "in_progress"

            if booking.checkout_current_step == 3 and booking.checkout_ending_km:

                booking.checkout_status = "completed"
                booking.checkout_completed_at = timezone.now()
                booking.checkout_completed_by = agent

                booking.checkout_final_total = (
                    (booking.quotation.total_price if booking.quotation else 0)
                    + booking.checkout_damage_charge
                    + booking.checkout_late_return_charge
                    + booking.checkout_extra_km_charge
                    + booking.checkout_fuel_charge
                    + booking.checkout_cleaning_fee
                )

            booking.save()

        return Response(
            CheckOutFullSerializer(
                booking,
                context={"request": request}
            ).data
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from .models import Fine
from .serializers import FineCreateSerializer, FineListSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_fine(request):
    """
    POST /api/v1/agency-agent/fines/
    """
    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agent"}, status=403)

    serializer = FineCreateSerializer(
        data=request.data,
        context={'request': request}
    )

    if serializer.is_valid():
        fine = serializer.save()
        return Response(FineListSerializer(fine, context={'request': request}).data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_fines_list(request):
    """
    ?booking_id=123 (optional filter)
    """
    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agent"}, status=403)

    agent = request.user.agent_profile

    queryset = Fine.objects.filter(created_by=agent)

    booking_id = request.query_params.get('booking_id')
    if booking_id:
        queryset = queryset.filter(rental_request__id=booking_id)

    serializer = FineListSerializer(queryset.order_by('-created_at'), many=True, context={'request': request})
    return Response({"fines": serializer.data})


from .serializers import AgentProfileSerializer, AgentProfileUpdateSerializer


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def agent_profile(request):
    """
    GET  → current agent's profile (with photo URL)
    PATCH → update name, phone, or upload profile photo
    """
    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agency agent"}, status=403)

    agent_profile = request.user.agent_profile

    if request.method == 'GET':
        serializer = AgentProfileSerializer(agent_profile, context={'request': request})
        return Response({
            "role": "agency_agent",
            "profile": serializer.data
        })

    data = request.data.copy()
    data.update(request.FILES)

    serializer = AgentProfileUpdateSerializer(
        agent_profile,
        data=data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()
        updated_serializer = AgentProfileSerializer(agent_profile, context={'request': request})
        return Response(updated_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from .serializers import DashboardBookingSerializer
from decimal import Decimal

from customers.models import Payment
from django.db.models import Sum
from datetime import timedelta
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_dashboard(request):
    if not hasattr(request.user, 'agent_profile'):
        return Response({"error": "Not an agency agent"}, status=403)

    agent = request.user.agent_profile

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timezone.timedelta(days=1)

    bookings = RentalRequest.objects.filter(car__assigned_agent=agent)

    todays_revenue = Payment.objects.filter(
        rental_request__car__assigned_agent=agent,
        status='completed',
        created_at__gte=today_start,
        created_at__lt=today_end
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    pending_bookings = bookings.filter(
        status__in=['pending', 'quotation_sent', 'awaiting_payment']
    ).count()


    today_active = bookings.filter(
        status='approved',
        pickup_date__lt=today_end,
        return_date__gt=today_start
    ).count()

    todays_checkin = bookings.filter(
        checkin_completed_at__gte=today_start,
        checkin_completed_at__lt=today_end,
        checkin_completed_at__isnull=False
    ).order_by('checkin_completed_at')

    todays_checkout = bookings.filter(
        checkout_completed_at__gte=today_start,
        checkout_completed_at__lt=today_end,
        checkout_completed_at__isnull=False
    ).order_by('checkout_completed_at')

    return Response({
        "todays_revenue": f"${todays_revenue:,.0f}",
        "pending_bookings": pending_bookings,
        "today_active": today_active,
        "todays_checkin": DashboardBookingSerializer(todays_checkin[:5], many=True).data,
        "todays_checkout": DashboardBookingSerializer(todays_checkout[:5], many=True).data,
    })