# RentHub Car Rental API

This is the backend API for the RentHub Car Rental platform. It is built using Django 6.0, Django REST Framework, Channels (for WebSockets), Celery (for background tasks), and Redis.

## Features
- **User Management**: Customer, Agency Admin, Agency Agent, Super Admin roles.
- **Car & Rental Management**: Agencies manage fleets; customers book cars.
- **Real-Time Chat**: Agents and customers can communicate regarding rentals via WebSockets.
- **Payments & Payouts**: Integrated with Stripe for bookings and monthly payout processing.

## Local Setup (Docker)

Dependencies:
- Docker & Docker Compose

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd car_rental
   ```

2. **Configure Environment:**
   ```bash
   cp .env_example .env
   # Edit .env and provide your local credentials
   ```

3. **Start Services:**
   ```bash
   docker-compose up --build
   ```
   This command starts the Web (Django/Uvicorn), Database (PostgreSQL), Redis, Celery worker, and Celery beat.

4. **Create Superuser (in another terminal):**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

The API will be available at `http://localhost:8000`.

## Production Deployment
Please refer to `deployment_guide.md` for deploying this project using Docker on a Ubuntu VPS.
