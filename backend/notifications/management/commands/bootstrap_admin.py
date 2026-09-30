import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from notifications.models import Profile

class Command(BaseCommand):
    help = 'Create an initial admin from ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD. Never resets an existing account.'
    def handle(self, *args, **kwargs):
        username = os.getenv('ADMIN_USERNAME')
        password = os.getenv('ADMIN_PASSWORD')
        email = os.getenv('ADMIN_EMAIL')
        if not all([username, password, email]):
            self.stdout.write('Admin bootstrap skipped; supply ADMIN_* variables or use createsuperuser.')
            return
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write('Admin already exists; no changes made.')
            return
        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except Exception as exc:
            raise CommandError('ADMIN_PASSWORD does not meet password validation requirements.') from exc
        user = User.objects.create_superuser(username=username, email=email, password=password)
        Profile.objects.create(user=user)
        self.stdout.write(self.style.SUCCESS('Admin created. Remove ADMIN_PASSWORD from hosting environment after initial setup.'))
