from django.urls import path, include
from . import views

urlpatterns = [
    path('agents/', views.agent_create_view, name='agent-create'),
    path('agents/list/', views.agency_agents_list, name='agency-agents-list'),
    
    path('agents/<int:pk>/', views.agency_agent_detail, name='agency-agent-detail'),
    path('cars/', views.add_car_view, name='add-car'),
    path('cars/<int:car_id>/', views.update_car_view, name='update-car'),
    
    path('bookings/', views.agency_booking_list, name='agency-booking-list'),
    path('bookings/<int:pk>/', views.agency_booking_detail, name='agency-booking-detail'),
    
    path('customers/', views.agency_customer_list, name='agency-customer-list'),
    path('customers/<int:pk>/', views.agency_customer_detail, name='agency-customer-detail'),
    path('customers/<int:pk>/vip/', views.agency_customer_vip_toggle, name='agency-customer-vip-toggle'),
    
    path('quotations/', views.agency_quotation_list, name='agency-quotation-list'),
    path('quotations/<int:pk>/', views.agency_quotation_detail, name='agency-quotation-detail'),
    
    path('payments-deposits/', views.agency_payments_deposits, name='agency-payments-deposits'),
    
    path('reports-analytics/', views.agency_reports_analytics, name='agency-reports-analytics'),
    path('settings/', views.agency_settings, name='agency-settings'),
    
    path('dashboard/', views.agency_dashboard, name='agency-dashboard'),
    path('vehicle-activity/', views.vehicle_activity_overview, name='vehicle-activity-overview'),
    
]