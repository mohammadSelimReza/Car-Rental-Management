from django.urls import path
from . import views

urlpatterns = [
    path('rental-requests/', views.agent_rental_request_list, name='agent-request-list'),
    path('rental-requests/<int:pk>/', views.agent_rental_request_detail, name='agent-request-detail'),
    path('rental-requests/<int:pk>/reject/', views.reject_rental_request, name='agent-reject-request'),
    path('rental-requests/<int:request_id>/create-quotation/', views.create_quotation, name='create-quotation'),
    path('checkin-bookings/', views.agent_checkin_bookings, name='agent-checkin-list'),
    path('checkin-bookings/<int:pk>/', views.agent_checkin_detail, name='agent-checkin-detail'),
    path('checkout-bookings/<int:pk>/', views.agent_checkout_detail, name='agent-checkout-detail'),
    path('fines/create/', views.create_fine, name='agent-create-fine'),
    path('fines/', views.agent_fines_list, name='agent-fines-list'),
    path('profile/', views.agent_profile, name='agent-profile'),
    path('dashboard/', views.agent_dashboard, name='agent-dashboard'),
]