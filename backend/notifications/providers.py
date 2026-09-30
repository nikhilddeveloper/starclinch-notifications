import uuid
import requests
from django.conf import settings
from .variables import names, whatsapp_body, SAMPLES

class ProviderError(Exception):
    pass

def require(*keys):
    missing = [key for key in keys if not getattr(settings, key)]
    if missing:
        raise ProviderError('Missing configuration: ' + ', '.join(missing))

def api(method, url, headers, payload=None, params=None):
    try:
        response = requests.request(method, url, headers=headers, json=payload, params=params,
                                    timeout=settings.PROVIDER_TIMEOUT)
    except requests.Timeout as exc:
        raise ProviderError('Provider timed out; delivery is uncertain. Check provider before sending again.') from exc
    except requests.RequestException as exc:
        raise ProviderError('Provider connection failed. Check configuration and provider availability.') from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise ProviderError('Provider returned an invalid response.') from exc
    if not isinstance(data, dict):
        raise ProviderError('Provider returned an unexpected response.')
    if not response.ok or data.get('errors') or data.get('error') or data.get('ErrorCode', 0):
        # Never persist provider response bodies: they may contain tokens or recipient data.
        raise ProviderError(f'Provider rejected request (HTTP {response.status_code}). Check credentials, approval, sender and recipient in provider dashboard.')
    return data

def wa_url(identifier, suffix):
    return f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{identifier}/{suffix}'

def wa_headers():
    return {'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}'}

def sync_whatsapp(template):
    if settings.NOTIFICATIONS_DRY_RUN:
        return '', 'DRAFT', 'Dry run: approval requires a real Meta sandbox account.'
    require('WHATSAPP_ACCESS_TOKEN', 'WHATSAPP_BUSINESS_ACCOUNT_ID')
    provider_name = template.provider_name
    if not provider_name:
        provider_name = f'sc_{template.trigger.key}_{template.pk}_v{template.revision}_{uuid.uuid4().hex[:8]}'
        body = {'type': 'BODY', 'text': whatsapp_body(template.body)}
        placeholders = names(template.body)
        if placeholders:
            body['example'] = {'body_text': [[SAMPLES[template.variable_mappings[n]] for n in placeholders]]}
        data = api('POST', wa_url(settings.WHATSAPP_BUSINESS_ACCOUNT_ID, 'message_templates'), wa_headers(),
                   {'name': provider_name, 'language': template.language, 'category': template.category, 'components': [body]})
        return provider_name, data.get('status', 'PENDING'), ''
    data = api('GET', wa_url(settings.WHATSAPP_BUSINESS_ACCOUNT_ID, 'message_templates'), wa_headers(),
               params={'name': provider_name, 'fields': 'name,status,language'})
    match = next((item for item in data.get('data', []) if item.get('name') == provider_name and item.get('language') == template.language), None)
    if not match:
        raise ProviderError('Template not found at Meta. Check the business account and language.')
    return provider_name, match['status'], ''

def send(delivery):
    payload = delivery.snapshot
    if settings.NOTIFICATIONS_DRY_RUN or payload.get('dry_run', False):
        return 'simulated', '', 'Dry run only; no provider request or real notification.'
    if delivery.channel == 'email':
        require('POSTMARKAPP_TOKEN', 'POSTMARK_FROM_EMAIL')
        if delivery.recipient.lower() not in [v.lower() for v in settings.SANDBOX_EMAILS]:
            raise ProviderError('Recipient is not in SANDBOX_EMAILS.')
        data = api('POST', 'https://api.postmarkapp.com/email',
                   {'X-Postmark-Server-Token': settings.POSTMARKAPP_TOKEN},
                   {'From': settings.POSTMARK_FROM_EMAIL, 'To': delivery.recipient, 'Subject': payload['title'],
                    'TextBody': payload['body'], 'MessageStream': 'outbound'})
        message_id = data.get('MessageID')
    elif delivery.channel == 'whatsapp':
        require('WHATSAPP_ACCESS_TOKEN', 'PHONE_NUMBER_ID')
        if delivery.recipient not in settings.SANDBOX_PHONES:
            raise ProviderError('Recipient is not in SANDBOX_PHONES.')
        if payload['provider_status'] != 'APPROVED' or not payload['provider_name']:
            raise ProviderError('WhatsApp template must be synced and APPROVED before sending.')
        template = {'name': payload['provider_name'], 'language': {'code': payload['language']}}
        if payload['parameters']:
            template['components'] = [{'type': 'body', 'parameters': [{'type': 'text', 'text': value} for value in payload['parameters']]}]
        data = api('POST', wa_url(settings.PHONE_NUMBER_ID, 'messages'), wa_headers(),
                   {'messaging_product': 'whatsapp', 'to': delivery.recipient.lstrip('+'), 'type': 'template', 'template': template})
        message_id = next((m.get('id') for m in data.get('messages', []) if m.get('id')), None)
    else:
        require('ONESIGNAL_APP_ID', 'ONESIGNAL_REST_API_KEY')
        if delivery.recipient not in settings.SANDBOX_PUSH_IDS:
            raise ProviderError('Subscription is not in SANDBOX_PUSH_IDS. Copy your ID from the website profile.')
        data = api('POST', 'https://api.onesignal.com/notifications?c=push',
                   {'Authorization': f'Key {settings.ONESIGNAL_REST_API_KEY}'},
                   {'app_id': settings.ONESIGNAL_APP_ID, 'include_subscription_ids': [delivery.recipient],
                    'headings': {'en': payload['title']}, 'contents': {'en': payload['body']},
                    'isAnyWeb': True, 'isIos': False, 'isAndroid': False, 'idempotency_key': str(delivery.pk)})
        message_id = data.get('id')
    if not message_id:
        raise ProviderError('Provider did not return a message ID; acceptance could not be confirmed.')
    return 'accepted', str(message_id), 'Provider accepted request; verify actual receipt on the recipient device.'
