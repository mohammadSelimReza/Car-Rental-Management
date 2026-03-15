import random
from datetime import timedelta
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

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Generates 500+ data points for testing'

    def handle(self, *args, **options):
        self.stdout.write("Starting data generation...")
        PASSWORD = 'test_pass_123'

        with transaction.atomic():
            # Clear existing data to avoid unique constraint issues
            self.stdout.write("Clearing existing data...")
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
            User.objects.filter(role__in=['agency_admin', 'agency_agent', 'customer']).delete()

            # 1. Create Agencies
            agencies = []
            for i in range(5):
                name = fake.company()[:255]
                agency = Agency.objects.create(
                    name=name,
                    location=fake.address()[:255],
                    phone=fake.phone_number()[:20],
                    email=fake.email()[:254],
                    website=fake.url()[:200],
                    commission_rate=Decimal(random.randint(5, 15)),
                    status='active'
                )
                agencies.append(agency)
            self.stdout.write(f"Created {len(agencies)} Agencies")

            # 2. Create Users (Super Admin, Agency Admin, Agency Agent, Customer)
            all_users = []
            
            # Super Admin
            if not User.objects.filter(username='superadmin').exists():
                super_user = User.objects.create_superuser(
                    username='superadmin',
                    email='superadmin@example.com',
                    password=PASSWORD,
                    role='super_admin'
                )
                all_users.append(super_user)

            # Agency Admins (2 per agency)
            agency_admins = []
            for agency in agencies:
                for i in range(2):
                    username = f"admin_{agency.id}_{i}"
                    user = User.objects.create_user(
                        username=username,
                        email=fake.email()[:254],
                        password=PASSWORD,
                        role='agency_admin'
                    )
                    admin_profile = AgencyAdmin.objects.create(
                        user=user,
                        agency=agency,
                        name=fake.name()[:255],
                        phone_number=fake.phone_number()[:20]
                    )
                    agency_admins.append(admin_profile)
                    all_users.append(user)
            self.stdout.write(f"Created {len(agency_admins)} Agency Admins")

            # Agency Agents (4 per agency)
            agency_agents = []
            for agency in agencies:
                for i in range(4):
                    username = f"agent_{agency.id}_{i}"
                    user = User.objects.create_user(
                        username=username,
                        email=fake.email()[:254],
                        password=PASSWORD,
                        role='agency_agent'
                    )
                    agent_profile = AgencyAgent.objects.create(
                        user=user,
                        agency=agency,
                        name=fake.name()[:255],
                        phone_number=fake.phone_number()[:20]
                    )
                    agency_agents.append(agent_profile)
                    all_users.append(user)
            self.stdout.write(f"Created {len(agency_agents)} Agency Agents")

            # Customers (100)
            customers = []
            for i in range(100):
                username = f"customer_{i}"
                user = User.objects.create_user(
                    username=username,
                    email=fake.email()[:254],
                    password=PASSWORD,
                    role='customer'
                )
                customer_profile = Customer.objects.create(
                    user=user,
                    name=fake.name()[:255],
                    license_number=fake.bothify(text='??-#######')[:100],
                    license_expiry_date=fake.future_date(end_date='+3650d'),
                    id_passport_number=fake.bothify(text='PASS-#######')[:100],
                    phone_number=fake.phone_number()[:20],
                    license_status='verified'
                )
                customers.append(customer_profile)
                all_users.append(user)
            self.stdout.write(f"Created {len(customers)} Customers")

            # 3. Create Cars (20 per agency)
            cars = []
            categories = ['Economy', 'Compact', 'SUV', 'Luxury', 'Sports']
            transmissions = ['Manual', 'Automatic']
            fuel_types = ['Petrol', 'Diesel', 'Electric', 'Hybrid']
            
            for agency in agencies:
                agency_agents_list = list(agency.agents.all())
                for i in range(20):
                    car = Car.objects.create(
                        agency=agency,
                        car_name=fake.catch_phrase()[:255],
                        category=random.choice(categories),
                        transmission=random.choice(transmissions),
                        fuel_type=random.choice(fuel_types),
                        seats=random.choice([2, 4, 5, 7]),
                        doors=random.choice([2, 4, 5]),
                        price_per_day=Decimal(random.randint(30, 300)),
                        status='available',
                        color=fake.color_name()[:50],
                        license_plate=fake.license_plate()[:20],
                        mileage=random.randint(1000, 100000),
                        assigned_agent=random.choice(agency_agents_list) if agency_agents_list else None
                    )
                    cars.append(car)
            self.stdout.write(f"Created {len(cars)} Cars")

            # 4. Create Extra Services (10 per agency)
            extra_services = []
            for agency in agencies:
                for i in range(10):
                    service = ExtraService.objects.create(
                        agency=agency,
                        name=fake.word().capitalize() + " Service",
                        description=fake.sentence(),
                        price_per_day=Decimal(random.randint(5, 50))
                    )
                    extra_services.append(service)
            self.stdout.write(f"Created {len(extra_services)} Extra Services")

            # 5. Create Rental Requests (150)
            status_choices = ['pending', 'approved', 'completed', 'cancelled']
            rental_requests = []
            for i in range(150):
                car = random.choice(cars)
                customer_user = random.choice(customers).user
                pickup = timezone.now() + timedelta(days=random.randint(-30, 30))
                return_date = pickup + timedelta(days=random.randint(1, 14))
                
                request = RentalRequest.objects.create(
                    car=car,
                    customer=customer_user,
                    pickup_date=pickup,
                    return_date=return_date,
                    notes=fake.text(max_nb_chars=100),
                    status=random.choice(status_choices),
                    payment_status='pending'
                )
                
                # Add some random extra services
                agency_services = list(car.agency.extra_services.all())
                if agency_services:
                    request.extra_services.add(*random.sample(agency_services, k=random.randint(0, min(3, len(agency_services)))))
                
                rental_requests.append(request)
            self.stdout.write(f"Created {len(rental_requests)} Rental Requests")

            # 6. Create Quotations (100)
            quotations = []
            for i in range(100):
                request = rental_requests[i]
                agent = random.choice(list(request.car.agency.agents.all())) if request.car.agency.agents.exists() else None
                
                base_price = request.car.price_per_day * Decimal(request.total_days)
                extra_cost = sum(s.price_per_day for s in request.extra_services.all()) * Decimal(request.total_days)
                subtotal = base_price + extra_cost
                vat = subtotal * Decimal('0.22')
                total = subtotal + vat
                
                quotation = Quotation.objects.create(
                    rental_request=request,
                    created_by=agent,
                    base_price=base_price,
                    extra_services_cost=extra_cost,
                    subtotal=subtotal,
                    vat_percentage=Decimal('22.00'),
                    vat_amount=vat,
                    security_deposit=Decimal('500.00'),
                    total_price=total,
                    status='sent' if request.status != 'completed' else 'accepted'
                )
                quotations.append(quotation)
                
                if request.status == 'completed' or request.status == 'approved':
                    request.status = 'approved' if request.status == 'approved' else 'completed'
                    request.save()
            self.stdout.write(f"Created {len(quotations)} Quotations")

            # 7. Create Payments (80)
            payments = []
            for i in range(80):
                request = rental_requests[i]
                if hasattr(request, 'quotation'):
                    payment = Payment.objects.create(
                        rental_request=request,
                        amount=request.quotation.total_price,
                        stripe_payment_intent_id=fake.bothify(text='pi_########################'),
                        status='completed'
                    )
                    request.payment_status = 'paid'
                    request.save()
                    payments.append(payment)
            self.stdout.write(f"Created {len(payments)} Payments")

            # 8. Create Fines (30)
            fine_types = ['speeding_violation', 'parking_violation', 'vehicle_damage']
            fines = []
            for i in range(30):
                request = random.choice([r for r in rental_requests if r.status == 'completed'])
                agent = random.choice(list(request.car.agency.agents.all())) if request.car.agency.agents.exists() else None
                fine = Fine.objects.create(
                    rental_request=request,
                    fine_type=random.choice(fine_types),
                    amount=Decimal(random.randint(50, 500)),
                    due_date=timezone.now().date() + timedelta(days=30),
                    reason=fake.sentence(),
                    created_by=agent,
                    status='pending'
                )
                fines.append(fine)
            self.stdout.write(f"Created {len(fines)} Fines")

            # 9. Create Car Reviews (50)
            reviews = []
            for i in range(50):
                car = random.choice(cars)
                customer_user = random.choice(customers).user
                # Ensure no duplicate reviews for same user and car
                if not CarReview.objects.filter(car=car, user=customer_user).exists():
                    review = CarReview.objects.create(
                        car=car,
                        user=customer_user,
                        rating=random.randint(3, 5),
                        comment=fake.paragraph()
                    )
                    reviews.append(review)
            self.stdout.write(f"Created {len(reviews)} Car Reviews")

            self.stdout.write(self.style.SUCCESS(f"Successfully generated 500+ data points!"))
            self.stdout.write(f"Summary:")
            self.stdout.write(f"- Agencies: {Agency.objects.count()}")
            self.stdout.write(f"- Users: {User.objects.count()}")
            self.stdout.write(f"- Customers: {Customer.objects.count()}")
            self.stdout.write(f"- Cars: {Car.objects.count()}")
            self.stdout.write(f"- Rental Requests: {RentalRequest.objects.count()}")
            self.stdout.write(f"- Quotations: {Quotation.objects.count()}")
            self.stdout.write(f"- Payments: {Payment.objects.count()}")
            self.stdout.write(f"- Fines: {Fine.objects.count()}")
            self.stdout.write(f"- Car Reviews: {CarReview.objects.count()}")
