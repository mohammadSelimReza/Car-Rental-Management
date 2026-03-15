# Makefile for Car Rental Management Project

.PHONY: help up down build restart logs migrate static superuser shell test clean deploy

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
