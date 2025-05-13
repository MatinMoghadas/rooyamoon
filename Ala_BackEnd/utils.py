import re
import secrets
import logging
import httpx
from urllib.parse import quote
from django.conf import settings
from django.core.cache import cache
import redis
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

# Define timeout settings for the HTTP request
timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)


def generate_otp(length=5):
    """Generate a random OTP of specified length."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def send_otp(mobile_phone_number, otp):
    """Send OTP via external SMS API using Django settings"""

    sms_api_url = settings.SMS_API_URL
    username = settings.SMS_API_USERNAME
    password = settings.SMS_API_PASSWORD
    from_num = settings.SMS_API_FROM_NUMBER

    message = f"""
    کد ورود به پلتفرم رویامون
    @pnapi.ir\n#{otp}
    """
    encoded_message = quote(message.strip())

    try:
        with httpx.Client() as client:
            response = client.get(
                f"{sms_api_url}?username={username}&password={password}"
                f"&from={from_num}&to={mobile_phone_number}&text={encoded_message}",
                timeout=settings.SMS_TIMEOUT
            )
            result = response.text
            if result == "SendWasSuccessful":
                logger.info(f"OTP {otp} sent to {mobile_phone_number} successfully.")
                return True
            logger.error(f"Failed to send OTP to {mobile_phone_number}. API Response: {result}")
            return False
    except Exception as e:
        logger.error(f"Error sending OTP to {mobile_phone_number}: {str(e)}")
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
    usernames = set(re.findall(r'@(\w+)', content))
    users = User.objects.filter(username__in=usernames)
    return users