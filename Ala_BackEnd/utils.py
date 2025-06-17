import re
import secrets
import logging
import httpx
import requests
from django.conf import settings
from django.core.cache import cache
import redis
from django.utils import timezone
from requests.auth import HTTPBasicAuth
from django.contrib.auth import get_user_model
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

# Define timeout settings for the HTTP request
timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)


def generate_otp(length=5):
    """Generate a random OTP of specified length."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def send_otp_sms(phone_number: str, otp: str) -> bool:
    url = "https://smspanel.trez.ir/api/smsApiWithPattern/SendCode"

    payload = {
        "AccessHash": settings.TREZ_ACCESS_HASH,
        "PatternId": settings.TREZ_PATTERN_ID,
        "token1": otp,
        "Mobile": phone_number
    }

    try:
        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth("09197230398", "MIRHEIDARY@#")
        )
        result = response.json()
        return result

    except Exception as e:
        print(f"Failed to send SMS: {e}")
        return False


def store_otp_in_redis(mobile_phone_number, otp, timeout=300):
    """Stores OTP in Redis with a timeout (default 5 minutes)"""
    cache.set(f"otp:{mobile_phone_number}", otp, timeout)


def get_otp_from_redis(mobile_phone_number):
    """Retrieve OTP from Redis with error handling"""
    try:
        return cache.get(f"otp:{mobile_phone_number}")
    except redis.ConnectionError:
        logger.error(f"Redis connection error while retrieving OTP for {mobile_phone_number}")
        return None


def verify_otp(mobile_phone_number, otp):
    """Verify the OTP entered by the user"""
    stored_otp = get_otp_from_redis(mobile_phone_number)
    if not stored_otp or str(stored_otp) != str(otp):
        return False
    cache.delete(f"otp:{mobile_phone_number}")  # Remove OTP after verification
    return True


def get_or_create_user(mobile_phone_number):
    """Retrieve existing user or create a new one"""
    user, created = User.objects.get_or_create(mobile_phone_number=mobile_phone_number)
    return user


def generate_tokens_for_user(user):
    """
    Generates JWT access and refresh tokens for the given user.
    """
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh)
    }


def get_display_username(user):
    if user and user.username:
        return user.username
    return f"user number {user.id}"


def extract_mentions(content):
    # Normalize content by making it lowercase to support case-insensitive matching
    usernames = set(re.findall(r'@(\w+)', content.lower()))  # Convert content to lowercase
    # Look for users matching any of the extracted usernames (case-insensitive)
    users = User.objects.filter(username__in=usernames)
    return users


def ensure_bot_user():
    """
    Ensures that a bot user with the name 'بات تحلیلگر آرزو' exists.
    Creates one if it doesn't.
    Returns the User instance.
    """
    bot_username = "بات تحلیلگر آرزو"

    bot_user, created = User.objects.get_or_create(
        username=bot_username,
        defaults={
            "mobile_phone_number": None,
            "Full_name": bot_username,
            "bio": "من یک ربات تحلیل‌گر هستم که توسط هوش مصنوعی تغذیه می‌شوم.",
            "is_bot": True,
            "created_at": timezone.now(),
            "is_active": True,
            "which_social_media": "site",
        }
    )
    return bot_user