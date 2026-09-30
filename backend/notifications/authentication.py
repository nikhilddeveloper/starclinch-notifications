from datetime import timedelta
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token.created < timezone.now() - timedelta(hours=12):
            token.delete()
            raise AuthenticationFailed('Session expired. Please log in again.')
        return user, token
