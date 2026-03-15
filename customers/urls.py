from django.urls import path
from . import views

urlpatterns = [
    path('cars/', views.customer_car_list, name='customer-car-list'),
    path('cars/<int:pk>/', views.customer_car_detail, name='customer-car-detail'),
    
    path('rental-requests/', views.customer_rental_requests, name='customer-rental-requests'),
    path('rental-requests/create/', views.create_rental_request, name='create-rental-request'),
    path('rental-requests/<int:pk>/', views.rental_request_detail, name='rental-request-detail'),
    
    path("pay-booking/<int:rental_request_id>/", views.pay_booking, name="pay-booking"),
    path('stripe/webhook_for_rental_booking/', views.stripe_webhook_for_rental_booking, name='stripe-webhook-for-rental-booking'),
    
    path('quotations/<int:quotation_id>/accept/', views.accept_quotation, name='accept-quotation'),
    path('driving-license/', views.customer_driving_license, name='customer-driving-license'),
    
    path('profile/', views.customer_profile, name='customer-profile'),
    path('fines-invoices/', views.customer_fines_invoices, name='customer-fines-invoices'),
    
    path('fines-invoices/<int:fine_id>/download/', views.download_invoice, name='download-invoice'),

    path('fines-invoices/<int:fine_id>/pay/', views.pay_fine, name='pay-fine'),
    
    path('stripe/webhook/', views.stripe_webhook, name='stripe-webhook'),
]