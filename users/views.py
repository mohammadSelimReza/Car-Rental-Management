from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


from django.conf import settings
from django.core.mail import send_mail
import random
import string

from .models import User, Customer, AgencyAgent
from .serializers import CustomerSignUpSerializer, CustomerDetailSerializer, UserSerializer, AgencyAgentSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_signup(request):
    serializer = CustomerSignUpSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        
        email = serializer.validated_data.get('email')
        user = User.objects.get(email=email)
        
        otp = ''.join(random.choices(string.digits, k=6))
        user.otp = otp
        user.is_active = False
        user.save()
        
        subject = 'Your OTP for Email Verification'
        message = f'Hello, your OTP to verify your email is: {otp}.'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        send_mail(subject, message, from_email, recipient_list)
        
        return Response({
            'message': 'Signup successful. Please verify OTP sent to your email.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    email = request.data.get('email')
    otp = request.data.get('otp')

    if not email or not otp:
        return Response({"detail": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"detail": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

    if user.otp != otp:
        return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

    if user.is_active:
        return Response({"detail": "This account is already verified."}, status=status.HTTP_400_BAD_REQUEST)

    user.is_active = True
    user.otp = None 
    user.save()

    refresh = RefreshToken.for_user(user)
    
    return Response({
        'message': 'OTP verified successfully. Your account is now active.',
        'refresh_token': str(refresh),
        'access_token': str(refresh.access_token),
        'profile_data': CustomerDetailSerializer(user.customer_profile).data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    email = request.data.get('email')
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"detail": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

    if user.is_active:
        return Response({"detail": "This account is already verified."}, status=status.HTTP_400_BAD_REQUEST)

    otp = ''.join(random.choices(string.digits, k=6))
    user.otp = otp
    user.save()

    subject = 'Your New OTP for Email Verification'
    message = f'Hello, your new OTP to verify your email is: {otp}.'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    send_mail(subject, message, from_email, recipient_list)

    return Response({
        'message': 'A new OTP has been sent to your email.',
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=email, password=password)
    
    
    if not user:
        return Response({"detail": "Invalid credentials or account not verified."}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_active:
        return Response({"detail": "Please verify your account with OTP before logging in."}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    
    return Response({
        'refresh_token': str(refresh),
        'access_token': str(refresh.access_token),
        'email': str(email),
        'role':user.role,
        'message': 'Successfully authenticated.'
    }, status=status.HTTP_200_OK)

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def customer_profile(request):
    try:
        customer_profile = request.user.customer_profile
    except Customer.DoesNotExist:
        return Response({"detail": "Customer profile not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = CustomerDetailSerializer(customer_profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'PATCH':
        serializer = CustomerDetailSerializer(customer_profile, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'profile': serializer.data,
                'detail': 'Profile updated successfully.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    email = request.data.get('email')
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        return Response({"detail": "User with this email does not exist or is not active."}, status=status.HTTP_404_NOT_FOUND)

    otp = ''.join(random.choices(string.digits, k=6))
    user.otp = otp
    user.save()

    subject = 'Your Password Reset OTP'
    message = f'Hello, your OTP to reset your password is: {otp}'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    send_mail(subject, message, from_email, recipient_list)

    return Response({"detail": "OTP for password reset has been sent to your email."}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_forgot_password_otp(request):
    email = request.data.get('email')
    otp = request.data.get('otp')

    if not email or not otp:
        return Response({"detail": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        if user.otp == otp:
            return Response({"detail": "OTP is valid. You can now reset your password."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    email = request.data.get('email')
    otp = request.data.get('otp')
    new_password = request.data.get('password')

    if not email or not new_password or not otp:
        return Response({"detail": "Email, OTP, and new password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        if user.otp != otp:
            return Response({"detail": "Invalid or expired OTP. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.otp = None
        user.save()
        
        return Response({'message': 'Password reset successful. Please login with your new password.'}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not current_password or not new_password:
        return Response({"detail": "Both current and new passwords are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    if not user.check_password(current_password):
        return Response({"detail": "Your current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([AllowAny])
def social_login(request):
    email = request.data.get('email')
    name = request.data.get('name') or email
    role = request.data.get('role')
    auth_provider = request.data.get('auth_provider')

    if not email or not role or not auth_provider:
        return Response(
            {'error': 'Please provide email, role and auth_provider'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': email,
            'role': role,
            'is_active': True
        }
    )

    if user.role != role:
        user.role = role
        user.save()

    profile_data = None

    if role == 'agency_agent':

        agent_exists = AgencyAgent.objects.filter(user=user).exists()

        if not agent_exists:
            agent_profile = AgencyAgent(
                user=user,
                name=name,
                agency_name="Default Agency",
                agent_id=f"SOCIAL-{user.id}"
            )
            agent_profile.save()

        else:
            agent_profile = AgencyAgent.objects.get(user=user)
            agent_profile.name = name
            print(agent_profile.name)
            if not agent_profile.agent_id:
                agent_profile.agent_id = f"SOCIAL-{user.id}"
            agent_profile.save()

        profile_data = AgencyAgentSerializer(agent_profile).data

    elif role == 'customer':
        customer_profile, _ = Customer.objects.get_or_create(
            user=user,
            defaults={'name': name}
        )

        customer_profile.name = name
        customer_profile.save()

        profile_data = CustomerDetailSerializer(customer_profile).data

    else:
        profile_data = UserSerializer(user).data

    refresh = RefreshToken.for_user(user)

    return Response({
        "message": "Successfully authenticated",
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "profile_data": profile_data
    })
    
    
