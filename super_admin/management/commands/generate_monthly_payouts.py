from django.core.management.base import BaseCommand
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db.models import Sum, Count
from agency_admin.models import Agency
from customers.models import RentalRequest
from super_admin.models import CommissionPayout


class Command(BaseCommand):
    help = 'Generate monthly commission payout records for the previous month'

    def handle(self, *args, **options):
        today = timezone.now().date()
        prev_month = today - relativedelta(months=1)

        period_year = prev_month.year
        period_month = prev_month.month

        period_start = timezone.make_aware(timezone.datetime.combine(prev_month.replace(day=1), timezone.datetime.min.time()))
        period_end = timezone.make_aware(timezone.datetime.combine(
            (period_start + relativedelta(months=1) - relativedelta(days=1)),
            timezone.datetime.max.time()
        ))

        self.stdout.write(
            self.style.NOTICE(
                f"Generating payouts for {period_start.strftime('%B %Y')} "
                f"({period_start} → {period_end})"
            )
        )

        created_count = 0
        skipped_count = 0

        for agency in Agency.objects.filter(status='active'):
            if CommissionPayout.objects.filter(
                agency=agency,
                period_year=period_year,
                period_month=period_month
            ).exists():
                skipped_count += 1
                continue

            bookings = RentalRequest.objects.filter(
                car__agency=agency,
                payment_status='paid',
                pickup_date__lte=period_end,
                return_date__gte=period_start
            )

            if not bookings.exists():
                continue 

            total_revenue = bookings.aggregate(
                total=Sum('quotation__total_price') if hasattr(bookings.first(), 'quotation') else Sum('total_price')
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

            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Created {created_count} new payout records, "
                f"skipped {skipped_count} (already exist)"
            )
        )