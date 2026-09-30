from django.core.management.base import BaseCommand
from notifications.models import Trigger, NotificationTemplate

class Command(BaseCommand):
    help = 'Create two triggers and six templates without overwriting existing edits.'
    def handle(self, *args, **kwargs):
        for key, name, body in [('login', 'Login', 'Hello {{name}}, you signed in successfully. Welcome back.'),
                                ('logout', 'Logout', 'Hello {{name}}, you signed out successfully. See you again soon.')]:
            trigger, _ = Trigger.objects.get_or_create(key=key, defaults={'name': name, 'description': f'Fires when a user completes {key} on the website.'})
            for channel in ['whatsapp', 'email', 'push']:
                NotificationTemplate.objects.get_or_create(trigger=trigger, channel=channel, defaults={
                    'title': f'{name} confirmation' if channel != 'whatsapp' else '', 'body': body,
                    'variable_mappings': {'name': 'user.name'}, 'enabled': True})
        self.stdout.write(self.style.SUCCESS('Login and Logout templates ready. Configure your profile before testing.'))
