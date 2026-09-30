from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Delivery, NotificationEvent, Profile, Trigger
from .variables import render, names
from .providers import send, ProviderError

def dispatch(delivery_id):
    # Conditional claim is atomic across web processes and the optional worker.
    claimed = Delivery.objects.filter(pk=delivery_id, status='queued').update(status='sending', updated_at=timezone.now())
    if not claimed:
        return
    delivery = Delivery.objects.get(pk=delivery_id)
    try:
        status, message_id, detail = send(delivery)
    except ProviderError as exc:
        status, message_id, detail = 'failed', '', str(exc)
    except Exception:
        status, message_id, detail = 'failed', '', 'Unexpected provider error. Check server configuration.'
    Delivery.objects.filter(pk=delivery_id).update(status=status, provider_message_id=message_id,
                                                   detail=detail, updated_at=timezone.now())

def drain(ids):
    for delivery_id in ids:
        dispatch(delivery_id)

@transaction.atomic
def fire_event(key, user, deduplication_key, test_template=None):
    event, created = NotificationEvent.objects.get_or_create(deduplication_key=deduplication_key,
        defaults={'trigger_key': key, 'user': user, 'is_test': test_template is not None})
    if not created:
        return event
    trigger = Trigger.objects.filter(key=key).first()
    if not trigger:
        return event
    profile, _ = Profile.objects.get_or_create(user=user)
    context = {'user.name': user.first_name or user.username, 'user.email': user.email,
               'event.name': trigger.name, 'event.time': timezone.now().strftime('%Y-%m-%d %H:%M UTC')}
    templates = [test_template] if test_template else list(trigger.templates.all())
    ids = []
    for template in templates:
        reason = ''
        if not trigger.enabled or not template.enabled:
            reason = 'Trigger or channel is disabled.'
        if template.channel == 'email':
            recipients = [user.email]
            if not profile.email_consent:
                reason = reason or 'Email consent is off.'
        elif template.channel == 'whatsapp':
            recipients = [profile.phone]
            if not profile.whatsapp_consent:
                reason = reason or 'WhatsApp consent is off.'
        else:
            recipients = [str(value) for value in user.push_subscriptions.values_list('subscription_id', flat=True)] or ['']
        snapshot = {'dry_run': settings.NOTIFICATIONS_DRY_RUN, 'title': render(template.title, template.variable_mappings, context),
                    'body': render(template.body, template.variable_mappings, context),
                    'provider_name': template.provider_name, 'provider_status': template.provider_status,
                    'language': template.language, 'revision': template.revision,
                    'parameters': [str(context[template.variable_mappings[n]]) for n in names(template.body)]}
        for recipient in recipients:
            skip = reason or ('No recipient / browser subscription configured.' if not recipient else '')
            delivery = Delivery.objects.create(event=event, template=template, channel=template.channel,
                recipient=recipient, snapshot=snapshot, status='skipped' if skip else 'queued', detail=skip)
            if not skip:
                ids.append(delivery.pk)
    if settings.NOTIFICATIONS_INLINE:
        transaction.on_commit(lambda: drain(ids))
    return event
