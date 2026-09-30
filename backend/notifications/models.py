import uuid
from django.conf import settings
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=16, blank=True)
    email_consent = models.BooleanField(default=False)
    whatsapp_consent = models.BooleanField(default=False)

class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions')
    subscription_id = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Trigger(models.Model):
    key = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['id']
    def __str__(self):
        return self.name

class NotificationTemplate(models.Model):
    CHANNELS = [('whatsapp', 'WhatsApp'), ('email', 'Email'), ('push', 'Web Push')]
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, related_name='templates')
    channel = models.CharField(max_length=10, choices=CHANNELS)
    title = models.CharField(max_length=160, blank=True)
    body = models.TextField(max_length=4000)
    variable_mappings = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default='en_US')
    category = models.CharField(max_length=20, choices=[('UTILITY', 'Utility'), ('MARKETING', 'Marketing')], default='UTILITY')
    revision = models.PositiveIntegerField(default=1)
    provider_name = models.CharField(max_length=160, blank=True)
    provider_status = models.CharField(max_length=30, default='DRAFT')
    provider_error = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['trigger', 'channel'], name='one_template_per_channel_trigger')]
    def __str__(self):
        return f'{self.trigger.key}: {self.channel}'

class NotificationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    trigger_key = models.CharField(max_length=60)
    deduplication_key = models.CharField(max_length=150, unique=True)
    is_test = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Delivery(models.Model):
    STATUSES = [(s, s) for s in ['queued', 'sending', 'accepted', 'simulated', 'failed', 'skipped']]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(NotificationEvent, on_delete=models.CASCADE, related_name='deliveries')
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True)
    channel = models.CharField(max_length=10)
    status = models.CharField(max_length=12, choices=STATUSES, default='queued')
    recipient = models.CharField(max_length=320, blank=True)
    snapshot = models.JSONField(default=dict)
    provider_message_id = models.CharField(max_length=300, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'created_at'])]
        constraints = [models.UniqueConstraint(fields=['event', 'channel', 'recipient'], name='unique_event_delivery')]
