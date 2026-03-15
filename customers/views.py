from django.shortcuts import render
import stripe
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import RentalRequest, Payment
from agency_admin.models import Car, ExtraService
from .serializers import (
    CarListSerializer, CarDetailSerializer,
    CreateRentalRequestSerializer, RentalRequestSerializer,
    PaymentIntentSerializer
)

stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(['GET'])
@permission_classes([AllowAny])
def customer_car_list(request):
    cars = Car.objects.filter(status='available')
    
    category = request.query_params.get('category')
    transmission = request.query_params.get('transmission')
    min_price = request.query_params.get('min_price')
    max_price = request.query_params.get('max_price')
    seats = request.query_params.get('seats')
    pickup_date = request.query_params.get('pickup_date')
    return_date = request.query_params.get('return_date')
    
    if category:
        cars = cars.filter(category=category)
    if transmission:
        cars = cars.filter(transmission=transmission)
    if min_price:
        cars = cars.filter(price_per_day__gte=min_price)
    if max_price:
        cars = cars.filter(price_per_day__lte=max_price)
    if seats:
        cars = cars.filter(seats__gte=seats)
    
    if pickup_date and return_date:
        conflicting_ids = RentalRequest.objects.filter(
            status__in=['pending', 'approved'],
            pickup_date__lt=return_date,
            return_date__gt=pickup_date
        ).values_list('car_id', flat=True)
        cars = cars.exclude(id__in=conflicting_ids)
    
    paginator = PageNumberPagination()
    paginator.page_size = int(request.GET.get('page_size', 10))
    result_page = paginator.paginate_queryset(cars, request)
    serializer = CarListSerializer(result_page, many=True, context={'request': request})
    
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def customer_car_detail(request, pk):
    car = get_object_or_404(Car, pk=pk)
    serializer = CarDetailSerializer(car, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_rental_request(request):
    serializer = CreateRentalRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        data = serializer.validated_data
        car = get_object_or_404(Car, id=data['car_id'])

        rental_request = RentalRequest.objects.create(
            car=car,
            customer=request.user,
            pickup_date=data['pickup_date'],
            return_date=data['return_date'],
            notes=data.get('notes', ''),
            status='pending',
            payment_status='pending'
        )
        
        if data.get('service_ids'):
            services = ExtraService.objects.filter(id__in=data['service_ids'])
            rental_request.extra_services.set(services)
        
        response_serializer = RentalRequestSerializer(rental_request)
        return Response(
            {
                "message": "Rental request created successfully",
                "request": response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from agency_agent.models import Quotation
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_quotation(request, quotation_id):
    quotation = Quotation.objects.get(id=quotation_id, rental_request__customer=request.user)
    
    if quotation.rental_request.status != 'quotation_sent':
        return Response({"error": "This quotation cannot be accepted at this time."}, status=status.HTTP_400_BAD_REQUEST)

    # Update statuses
    quotation.status = 'accepted'
    quotation.save()
    
    rental_request = quotation.rental_request
    rental_request.status = 'awaiting_payment'
    rental_request.save()
    
    return Response({"message": "Quotation accepted. Please proceed with payment."})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pay_booking(request, rental_request_id):

    rental_request = get_object_or_404(
        RentalRequest,
        id=rental_request_id,
        customer=request.user,
        status="awaiting_payment"
    )

    amount = rental_request.quotation.total_price

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",

            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Car Rental - {rental_request.car.car_name}",
                    },
                    "unit_amount": int(amount * 100),
                },
                "quantity": 1,
            }],

            success_url=settings.FRONTEND_URL,
            cancel_url=settings.FRONTEND_URL,

            metadata={
                "rental_request_id": str(rental_request.id),
                "customer_id": str(request.user.id),
            }
        )

        return Response({
            "checkout_url": session.url
        })

    except stripe.error.StripeError as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
stripe.api_key = settings.STRIPE_SECRET_KEY

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def stripe_webhook_for_rental_booking(request):

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET_FOR_RENTAL_BOOKING
        )
    except Exception as e:
        logger.error(e)
        return HttpResponse(status=400)

    # Checkout success
    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        rental_request_id = session["metadata"].get("rental_request_id")

        try:
            rental_request = RentalRequest.objects.get(id=rental_request_id)

            if rental_request.payment_status != "paid":

                rental_request.payment_status = "paid"
                rental_request.status = "approved"
                rental_request.payment_intent_id = session["payment_intent"]
                rental_request.save()

                Payment.objects.create(
                    rental_request=rental_request,
                    amount=session["amount_total"] / 100,
                    stripe_payment_intent_id=session["payment_intent"],
                    status="completed"
                )

        except RentalRequest.DoesNotExist:
            logger.error("RentalRequest not found")

    return HttpResponse(status=200)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_rental_requests(request):
    rental_requests = RentalRequest.objects.filter(customer=request.user).order_by('-created_at')
    serializer = RentalRequestSerializer(rental_requests, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rental_request_detail(request, pk):
    rental_request = get_object_or_404(RentalRequest, pk=pk, customer=request.user)
    serializer = RentalRequestSerializer(rental_request)
    return Response(serializer.data)


from .serializers import LicenseDetailSerializer, LicenseUpdateSerializer


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def customer_driving_license(request):
    customer = request.user.customer_profile

    if request.method == 'GET':
        serializer = LicenseDetailSerializer(customer, context={'request': request})
        return Response({
            "status": customer.license_status,
            "details": serializer.data
        })

    data = request.data.copy()
    data.update(request.FILES)

    serializer = LicenseUpdateSerializer(
        customer,
        data=data,
        partial=True,
        context={'request': request}
    )

    if serializer.is_valid():
        serializer.save()
        updated_serializer = LicenseDetailSerializer(customer, context={'request': request})
        return Response(updated_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



from .serializers import CustomerProfileSerializer, CustomerProfileUpdateSerializer


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def customer_profile(request):
    if not hasattr(request.user, 'customer_profile'):
        return Response({"error": "Not a customer"}, status=403)

    customer = request.user.customer_profile

    if request.method == 'GET':
        serializer = CustomerProfileSerializer(customer, context={'request': request})
        return Response({
            "role": "customer",
            "profile": serializer.data
        })

    data = request.data.copy()
    data.update(request.FILES)

    serializer = CustomerProfileUpdateSerializer(
        customer,
        data=data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()
        updated_serializer = CustomerProfileSerializer(customer, context={'request': request})
        return Response(updated_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from .serializers import FineSerializer
from agency_agent.models import Fine
from django.db.models import Sum

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_fines_invoices(request):
    if not hasattr(request.user, 'customer_profile'):
        return Response({"error": "Not a customer"}, status=403)

    fines = Fine.objects.filter(rental_request__customer=request.user)

    total_outstanding = fines.filter(status='pending').aggregate(
        total=Sum('amount')
    )['total'] or 0

    pending_count = fines.filter(status='pending').count()
    paid_count = fines.filter(status='paid').count()

    serializer = FineSerializer(
        fines.order_by('-created_at'),
        many=True,
        context={'request': request}
    )

    return Response({
        "total_outstanding": f"${total_outstanding:,.2f}",
        "pending_count": pending_count,
        "paid_count": paid_count,
        "fines": serializer.data
    })
    
from django.http import FileResponse, Http404    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_invoice(request, fine_id):
    """
    GET /api/customer/fines-invoices/<fine_id>/download/
    Download the invoice PDF/file for a specific fine
    """
    if not hasattr(request.user, 'customer_profile'):
        return Response({"error": "Not a customer"}, status=403)

    fine = get_object_or_404(Fine, id=fine_id, rental_request__customer=request.user)

    if not fine.invoice_file:
        return Response({"error": "No invoice file available for this fine"}, status=404)

    try:
        response = FileResponse(
            fine.invoice_file.open('rb'),
            as_attachment=True,
            filename=f"invoice-fine-{fine.id}.pdf"
        )
        return response
    except Exception as e:
        return Response({"error": f"Error downloading file: {str(e)}"}, status=500)

stripe.api_key = settings.STRIPE_SECRET_KEY
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_fine(request, fine_id):

    if not hasattr(request.user, 'customer_profile'):
        return Response({"error": "Not a customer"}, status=status.HTTP_403_FORBIDDEN)

    fine = get_object_or_404(
        Fine,
        id=fine_id,
        rental_request__customer=request.user
    )

    if fine.status == "paid":
        return Response({"error": "Fine already paid"}, status=status.HTTP_400_BAD_REQUEST)

    if fine.status == "waived":
        return Response({"error": "Fine has been waived"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount_cents = int(fine.amount * 100)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",

            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Fine #{fine.id}",
                        "description": fine.reason or "Fine payment",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],

            success_url=settings.FRONTEND_URL,
            cancel_url=settings.FRONTEND_URL,

            metadata={
                "fine_id": str(fine.id),
                "customer_id": str(request.user.id),
                "booking_id": str(fine.rental_request.id),
            },
        )

        return Response(
            {
                "checkout_url": session.url
            },
            status=status.HTTP_200_OK
        )

    except stripe.error.StripeError as e:
        return Response(
            {"error": e.user_message or "Stripe payment error"},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception:
        return Response(
            {"error": "Unable to create checkout session"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import stripe
import logging
logger = logging.getLogger(__name__)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return HttpResponse(status=400)

    # ✅ Correct event for Stripe Checkout
    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        fine_id = session["metadata"].get("fine_id")

        if fine_id:
            try:
                fine = Fine.objects.get(id=fine_id)

                if fine.status != "paid":
                    fine.status = "paid"
                    fine.paid_amount = fine.amount
                    fine.paid_at = timezone.now()
                    fine.save()

                    logger.info(f"Fine {fine_id} marked as PAID")

            except Fine.DoesNotExist:
                logger.error(f"Fine {fine_id} not found")

            except Exception as e:
                logger.error(f"Error updating fine {fine_id}: {e}")

    return HttpResponse(status=200)