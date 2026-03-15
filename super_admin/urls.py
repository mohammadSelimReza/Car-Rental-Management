from django.urls import path, include
from . import views

urlpatterns = [
    path('agencies/', views.agency_create_view, name='agency-list-create'),
    path('agencies/<int:agency_id>/', views.agency_detail, name='super-admin-agency-detail'),
    path('agencies/<int:agency_id>/commission/', views.update_agency_commission, name='update-agency-commission'),
    path('agencies/<int:agency_id>/suspend/', views.toggle_agency_suspension, name='toggle-agency-suspension'),
    path('global-pricing-rules/', views.global_pricing_rules_view, name='global-pricing-rules'),
    path('admins-agents/', views.super_admin_admins_agents_list, name='super-admins-agents-list'),
    path('admins-agents/admins/<int:pk>/toggle-active/', views.toggle_admin_active, name='toggle-admin-active'),
    path('admins-agents/agents/<int:pk>/toggle-active/', views.toggle_agent_active, name='toggle-agent-active'),
    path('users/', views.user_management_list, name='user-management-list'),
    path('users/<str:user_type>/<int:pk>/', views.user_detail, name='user-detail'),
    path('payments-commission/', views.payments_commission_overview, name='payments-overview'),
    path('payments-commission/payout/<int:payout_id>/', views.agency_payout_detail, name='payout-detail'),
    path('payments-commission/payout/<int:payout_id>/process/', views.create_account_and_payout, name='process-payout'),
    path('payments-commission/webhook/', views.stripe_webhook_for_payout, name='stripe-webhook-for-payout'),
    path('settings/general/', views.platform_settings, name='platform-settings'),
    path('settings/general/reset/', views.reset_platform_settings_to_defaults, name='reset-settings'),
    path('dashboard/', views.super_admin_dashboard, name='super-admin-dashboard'),
    path('agencies/list/', views.super_admin_agency_list, name='super-admin-agencies'),
    path('agencies/<int:agency_id>/toggle-status/', views.toggle_agency_status, name='toggle-agency-status'),
    path('customers/', views.super_admin_customers_list, name='super-admin-customers'),
    path('customers/<int:customer_id>/suspend/', views.toggle_customer_suspension, name='toggle-customer-suspension'),
    path('customers/<int:customer_id>/vip/', views.toggle_customer_vip, name='toggle-customer-vip'),
    path('customers/<int:customer_id>/flag/', views.toggle_customer_flag, name='toggle-customer-flag'),
    path('operation-overview/', views.super_admin_operation_overview, name='super-admin-operation-overview'),
]