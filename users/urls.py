from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views
urlpatterns = [

    path('signup/', views.customer_signup, name='signup'),
    path('login/', views.login, name='login'),
    path('social-login/', views.social_login, name='social_login'),

    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),

    path('profile/', views.customer_profile, name='user_profile'),

    path('password/forgot/', views.forgot_password, name='forgot_password'),
    path('password/verify-otp/', views.verify_forgot_password_otp, name='verify_forgot_password_otp'),
    path('password/reset/', views.reset_password, name='reset_password'),
    path('password/change/', views.change_password, name='change_password'),
    
    
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]