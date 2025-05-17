from django.contrib.auth.backends import BaseBackend
from .models import User

class CustomUserBackend(BaseBackend):
    def authenticate(self, request, mobile_phone_number=None):
        """Custom authentication using mobile_phone_number"""
        try:
            return User.objects.get(mobile_phone_number=mobile_phone_number)
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        """Get user by ID"""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
