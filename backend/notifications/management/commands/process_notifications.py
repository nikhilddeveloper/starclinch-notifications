import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from notifications.models import Delivery
from notifications.services import dispatch

class Command(BaseCommand):
    help = 'Drain queued deliveries. Use --once for one batch; otherwise poll every 2 seconds.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
    def handle(self, *args, **options):
        while True:
            close_old_connections()
            ids = list(Delivery.objects.filter(status='queued').order_by('created_at').values_list('id', flat=True)[:100])
            for delivery_id in ids:
                dispatch(delivery_id)
            if options['once']:
                return
            time.sleep(2)
