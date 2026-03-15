from rest_framework import serializers
from .models import User, Customer, AgencyAgent
from django.db import transaction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'role',
        )
        read_only_fields = ('id', 'username', 'role')

class CustomerSignUpSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = Customer
        fields = (
            'name',
            'email',
            'password',
            'license_image',
            'license_number',
            'license_expiry_date',
            'id_passport_number',
        )

    def validate_email(self, value):
        user = User.objects.filter(email__iexact=value).first()

        if user:
            if not user.is_active:
                Customer.objects.filter(user=user).delete()
                user.delete()
            else:
                raise serializers.ValidationError(
                    "A verified user with this email already exists."
                )

        return value

    @transaction.atomic
    def create(self, validated_data):
        user_data = {
            'email': validated_data.pop('email'),
            'password': validated_data.pop('password'),
        }
        
        user = User.objects.create_user(
            username=user_data['email'],
            email=user_data['email'],
            password=user_data['password'],
            role='customer'
        )

        customer = Customer.objects.create(user=user, **validated_data)
        
        return customer

class CustomerDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 

    class Meta:
        model = Customer
        fields = (
            'id',
            'name',
            'license_image',
            'license_number',
            'license_expiry_date',
            'id_passport_number',
            'created_at',
            'user'
        )
        
        
class AgencyAgentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = AgencyAgent
        fields = ('id', 'name', 'agency_name', 'agent_id', 'user')
    

