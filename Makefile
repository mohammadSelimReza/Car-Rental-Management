# Makefile for Car Rental Management Project

.PHONY: help up down build restart logs migrate static superuser shell test clean deploy generate-data list-users db-flush db-reset

# Default target
help:
	@echo "Available commands:"
	@echo "  make up         - Start all services with Docker Compose"
	@echo "  make down       - Stop all services"
	@echo "  make build      - Build or rebuild services"
	@echo "  make restart    - Restart web and celery services"
	@echo "  make logs       - View logs from all services"
	@echo "  make migrate    - Run database migrations"
	@echo "  make static     - Collect static files"
	@echo "  make superuser  - Create a Django superuser"
	@echo "  make shell      - Open a Django shell"
	@echo "  make test       - Run Django tests"
	@echo "  make clean      - Remove temporary files and caches"
	@echo "  make generate-data - Seed database with 500+ records"
	@echo "  make list-users  - List generated users with credentials"
	@echo "  make db-flush   - Clear all data from the database"
	@echo "  make db-reset   - Completely reset database (wipes volumes and re-migrates)"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart web celery celery-beat

logs:
	docker compose logs -f

migrate:
	docker compose exec web python manage.py migrate

static:
	docker compose exec web python manage.py collectstatic --noinput

superuser:
	docker compose exec web python manage.py createsuperuser

shell:
	docker compose exec web python manage.py shell

test:
	docker compose exec web python manage.py test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov

# Production shortcut
deploy: build up migrate static
	@echo "Deployment sequence completed."

generate-data:
	docker compose exec web python manage.py generate_data

list-users:
	@docker compose exec web python manage.py shell -c "from users.models import User; from django.db.models import Count; counts = User.objects.values('role').annotate(total=Count('id')); print('\nUser Generation Summary:'); print('-' * 40); [print(f'{c[\"role\"]: <20}: {c[\"total\"]} users') for c in counts]; print('-' * 40); print(f'{\"ROLE\":<15} | {\"USERNAME\":<20} | {\"EMAIL\":<30} | {\"PASSWORD\":<15}'); print('-' * 85); [print(f'{u.role:<15} | {u.username:<20} | {u.email:<30} | test_pass_123') for role in ['super_admin', 'agency_admin', 'agency_agent', 'customer'] for u in User.objects.filter(role=role)[:2]]; print('... [Showing 2 samples per role. Use Django Admin for full list]')"

db-flush:
	docker compose exec web python manage.py flush --noinput

db-reset:
	docker compose down -v
	docker compose up -d
	@sleep 5
	docker compose exec web python manage.py migrate
	@echo "Database has been reset and migrations reapplied."
