import random
from datetime import timedelta, date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from django.db import transaction
from django.contrib.auth import get_user_model

from users.models import Agency, AgencyAdmin, AgencyAgent, Customer
from agency_admin.models import Car, ExtraService
from customers.models import RentalRequest, Payment, CarReview
from agency_agent.models import Quotation, Fine
from super_admin.models import GlobalPricingRule, PlatformSettings, CommissionPayout
from chat.models import ChatRoom, ChatMessage

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Generates 1000+ data points for testing with full relations'

    def handle(self, *args, **options):
        self.stdout.write("Starting enhanced data generation...")
        PASSWORD = 'test_pass_123'

        with transaction.atomic():
            # Clear existing data
            self.stdout.write("Clearing existing data...")
            ChatMessage.objects.all().delete()
            ChatRoom.objects.all().delete()
            CommissionPayout.objects.all().delete()
            PlatformSettings.objects.all().delete()
            GlobalPricingRule.objects.all().delete()
            CarReview.objects.all().delete()
            Fine.objects.all().delete()
            Payment.objects.all().delete()
            Quotation.objects.all().delete()
            RentalRequest.objects.all().delete()
            ExtraService.objects.all().delete()
            Car.objects.all().delete()
            Customer.objects.all().delete()
            AgencyAgent.objects.all().delete()
            AgencyAdmin.objects.all().delete()
            Agency.objects.all().delete()
            User.objects.filter(role__in=['super_admin', 'agency_admin', 'agency_agent', 'customer']).delete()

            # 1. Platform Settings & Rules
            PlatformSettings.get_settings()
            GlobalPricingRule.objects.create(
                default_vat_tax=Decimal('22.00'),
                default_security_deposit=Decimal('500.00'),
                max_discount_limit=Decimal('25.00'),
                vip_discount_default=Decimal('10.00'),
                late_return_penalty=Decimal('50.00'),
                cancellation_policy="Full refund if cancelled 48h before."
            )
            self.stdout.write("Initialized Platform Settings and Pricing Rules")

            # 2. Create Agencies
            agencies = []
            for i in range(8):
                agency = Agency.objects.create(
                    name=fake.company()[:255],
                    location=fake.address()[:255],
                    phone=fake.phone_number()[:20],
                    email=fake.email()[:254],
                    website=fake.url()[:200],
                    commission_rate=Decimal(random.randint(5, 15)),
                    status='active'
                )
                agencies.append(agency)
            self.stdout.write(f"Created {len(agencies)} Agencies")

            # 3. Create Users
            # Super Admin
            if not User.objects.filter(email='superadmin@example.com').exists():
                User.objects.create_superuser(
                    username='superadmin@example.com', email='superadmin@example.com',
                    password=PASSWORD, role='super_admin'
                )

            # Agency Admins (2 per agency)
            agency_admins = []
            for agency in agencies:
                for i in range(2):
                    email = fake.email()[:254]
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=PASSWORD,
                        role='agency_admin'
                    )
                    agency_admins.append(AgencyAdmin.objects.create(
                        user=user, agency=agency, name=fake.name()[:255],
                        phone_number=fake.phone_number()[:20]
                    ))
            self.stdout.write(f"Created {len(agency_admins)} Agency Admins")

            # Agency Agents (4 per agency)
            agency_agents = []
            for agency in agencies:
                for i in range(5):
                    email = fake.email()[:254]
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=PASSWORD,
                        role='agency_agent'
                    )
                    agency_agents.append(AgencyAgent.objects.create(
                        user=user, agency=agency, name=fake.name()[:255],
                        phone_number=fake.phone_number()[:20]
                    ))
            self.stdout.write(f"Created {len(agency_agents)} Agency Agents")

            # Customers (200)
            customers = []
            for i in range(200):
                email = fake.email()[:254]
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=PASSWORD,
                    role='customer'
                )
                customers.append(Customer.objects.create(
                    user=user, name=fake.name()[:255],
                    license_number=fake.bothify(text='??-#######')[:100],
                    license_expiry_date=fake.future_date(end_date='+3650d'),
                    id_passport_number=fake.bothify(text='PASS-#######')[:100],
                    phone_number=fake.phone_number()[:20],
                    license_status='verified',
                    vip_status=random.choice([True, False, False, False])
                ))
            self.stdout.write(f"Created {len(customers)} Customers")

            # 4. Create Cars (20-25 per agency)
            cars = []
            categories = ['Economy', 'Compact', 'SUV', 'Luxury', 'Sports', 'Van']
            transmissions = ['Manual', 'Automatic']
            fuel_types = ['Petrol', 'Diesel', 'Electric', 'Hybrid']
            for agency in agencies:
                agents = list(agency.agents.all())
                for i in range(random.randint(20, 25)):
                    cars.append(Car.objects.create(
                        agency=agency, car_name=fake.catch_phrase()[:255],
                        category=random.choice(categories),
                        transmission=random.choice(transmissions),
                        fuel_type=random.choice(fuel_types),
                        seats=random.choice([2, 4, 5, 7, 9]),
                        doors=random.choice([2, 4, 5]),
                        price_per_day=Decimal(random.randint(35, 450)),
                        status='available', color=fake.color_name()[:50],
                        license_plate=fake.license_plate()[:20],
                        mileage=random.randint(500, 120000),
                        assigned_agent=random.choice(agents) if agents else None
                    ))
            self.stdout.write(f"Created {len(cars)} Cars")

            # 5. Extra Services
            for agency in agencies:
                for name in ["GPS", "Child Seat", "Insurance", "WiFi", "Driver"]:
                    ExtraService.objects.create(
                        agency=agency, name=name,
                        description=fake.sentence(),
                        price_per_day=Decimal(random.randint(10, 60))
                    )
            self.stdout.write("Created Extra Services for all agencies")

            # 6. Rental Requests (400)
            rental_requests = []
            for i in range(400):
                car = random.choice(cars)
                customer_user = random.choice(customers).user
                pickup = timezone.now() + timedelta(days=random.randint(-60, 60))
                return_date = pickup + timedelta(days=random.randint(1, 20))
                
                req = RentalRequest.objects.create(
                    car=car, customer=customer_user,
                    pickup_date=pickup, return_date=return_date,
                    notes=fake.text(max_nb_chars=100),
                    status=random.choice(['pending', 'approved', 'completed', 'cancelled', 'quotation_sent']),
                    payment_status='pending'
                )
                agency_services = list(car.agency.extra_services.all())
                if agency_services:
                    req.extra_services.add(*random.sample(agency_services, k=random.randint(0, 3)))
                rental_requests.append(req)
            self.stdout.write(f"Created {len(rental_requests)} Rental Requests")

            # 7. Quotations (300)
            for i in range(300):
                req = rental_requests[i]
                agent = random.choice(list(req.car.agency.agents.all())) if req.car.agency.agents.exists() else None
                base = req.car.price_per_day * Decimal(req.total_days)
                extra = sum(s.price_per_day for s in req.extra_services.all()) * Decimal(req.total_days)
                subtotal = base + extra
                vat = subtotal * Decimal('0.22')
                Quotation.objects.create(
                    rental_request=req, created_by=agent,
                    base_price=base, extra_services_cost=extra,
                    subtotal=subtotal, vat_percentage=Decimal('22.00'),
                    vat_amount=vat, security_deposit=Decimal('500.00'),
                    total_price=subtotal + vat,
                    status='accepted' if req.status in ['approved', 'completed'] else 'sent'
                )
                if req.status == 'quotation_sent':
                    req.status = 'quotation_sent'
                    req.save()
            self.stdout.write("Created 300 Quotations")

            # 8. Payments (250)
            for i in range(250):
                req = rental_requests[i]
                if hasattr(req, 'quotation'):
                    Payment.objects.create(
                        rental_request=req, amount=req.quotation.total_price,
                        stripe_payment_intent_id=fake.bothify(text='pi_########################'),
                        status='completed'
                    )
                    req.payment_status = 'paid'
                    req.save()
            self.stdout.write("Created 250 Payments")

            # 9. Fines (50)
            completed_reqs = [r for r in rental_requests if r.status == 'completed']
            for i in range(50):
                if not completed_reqs: break
                req = random.choice(completed_reqs)
                agent = random.choice(list(req.car.agency.agents.all())) if req.car.agency.agents.exists() else None
                Fine.objects.create(
                    rental_request=req, amount=Decimal(random.randint(50, 600)),
                    due_date=date.today() + timedelta(days=random.randint(5, 30)),
                    reason=fake.sentence(), created_by=agent,
                    fine_type=random.choice(['speeding_violation', 'parking_violation', 'vehicle_damage']),
                    status=random.choice(['pending', 'paid'])
                )
            self.stdout.write("Created 50 Fines")

            # 10. Car Reviews (100)
            for i in range(100):
                car = random.choice(cars)
                customer = random.choice(customers)
                if not CarReview.objects.filter(car=car, user=customer.user).exists():
                    CarReview.objects.create(
                        car=car, user=customer.user,
                        rating=random.randint(3, 5),
                        comment=fake.paragraph()
                    )
            self.stdout.write("Created 100 Car Reviews")

            # 11. Chat Rooms and Messages (100 rooms)
            for i in range(100):
                req = rental_requests[i]
                agent = random.choice(list(req.car.agency.agents.all())) if req.car.agency.agents.exists() else None
                if agent:
                    room, _ = ChatRoom.objects.get_or_create(
                        customer=req.customer, agent=agent.user, rental_request=req
                    )
                    for _ in range(random.randint(2, 8)):
                        sender = random.choice([req.customer, agent.user])
                        ChatMessage.objects.create(room=room, sender=sender, content=fake.sentence())
            self.stdout.write("Created Chats for 100 Rental Requests")

            # 12. Commission Payouts (Past 6 months for each agency)
            for agency in agencies:
                for m in range(1, 7):
                    CommissionPayout.objects.create(
                        agency=agency, period_year=2024, period_month=m,
                        period_start=date(2024, m, 1),
                        period_end=date(2024, m, 28),
                        total_bookings=random.randint(10, 50),
                        total_revenue=Decimal(random.randint(5000, 20000)),
                        commission_rate=agency.commission_rate,
                        commission_amount=Decimal(random.randint(500, 2000)),
                        status='completed', processed_at=timezone.now()
                    )
            self.stdout.write("Created Commission Payouts for all agencies")

            self.stdout.write(self.style.SUCCESS("Successfully generated 1500+ data points!"))
