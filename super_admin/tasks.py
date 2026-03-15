
from celery import shared_task
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count
from agency_admin.models import Agency
from customers.models import RentalRequest
from .models import CommissionPayout
from decimal import Decimal


@shared_task
def generate_monthly_payouts():
    today = timezone.now().date()
    prev_month = today - relativedelta(months=1)
    
    period_year = prev_month.year
    period_month = prev_month.month
    period_start = prev_month.replace(day=1)
    period_end = (period_start + relativedelta(months=1) - relativedelta(days=1))

    for agency in Agency.objects.filter(status='active'):
        if CommissionPayout.objects.filter(
            agency=agency,
            period_year=period_year,
            period_month=period_month
        ).exists():
            continue

        bookings = RentalRequest.objects.filter(
            car__agency=agency,
            payment_status='paid',
            pickup_date__lte=period_end,
            return_date__gte=period_start
        )

        total_revenue = bookings.aggregate(
            total=Sum('quotation__total_price') if bookings.exists() else 0
        )['total'] or Decimal('0.00')

        if total_revenue <= 0:
            continue 

        commission_rate = agency.commission_rate
        commission_amount = total_revenue * (commission_rate / Decimal('100'))
        processing_fee = Decimal('0.00')

        CommissionPayout.objects.create(
            agency=agency,
            period_year=period_year,
            period_month=period_month,
            period_start=period_start,
            period_end=period_end,
            total_bookings=bookings.count(),
            total_revenue=total_revenue,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            processing_fee=processing_fee,
            net_payout=commission_amount - processing_fee,
            status='pending'
        )