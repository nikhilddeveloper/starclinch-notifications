import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from notifications.models import Trigger, NotificationTemplate, Delivery, Profile, PushSubscription, NotificationEvent
from notifications.services import fire_event, dispatch
from notifications.providers import ProviderError

@override_settings(NOTIFICATIONS_DRY_RUN=True, NOTIFICATIONS_INLINE=True)
class NotificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('nikhil', email='nikhil@example.com', password='Strong-test-pass-472!', is_staff=True)
        self.profile = Profile.objects.create(user=self.user, phone='+919876543210', email_consent=True, whatsapp_consent=True)
        self.subscription = PushSubscription.objects.create(user=self.user, subscription_id=uuid.uuid4())
        call_command('seed_demo', verbosity=0)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.login_trigger = Trigger.objects.get(key='login')
        self.email = self.login_trigger.templates.get(channel='email')
    def fire(self, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return fire_event('login', self.user, kwargs.pop('key', str(uuid.uuid4())), **kwargs)
    def test_three_channels_simulated_without_network(self):
        with patch('notifications.providers.requests.request') as http:
            event = self.fire()
        self.assertEqual(set(event.deliveries.values_list('channel', flat=True)), {'email', 'whatsapp', 'push'})
        self.assertEqual(set(event.deliveries.values_list('status', flat=True)), {'simulated'})
        http.assert_not_called()
    def test_toggle_skips_only_one_channel(self):
        self.email.enabled = False
        self.email.save()
        event = self.fire()
        self.assertEqual(event.deliveries.get(channel='email').status, 'skipped')
        self.assertEqual(event.deliveries.filter(status='simulated').count(), 2)
    def test_trigger_toggle_skips_all_channels(self):
        self.login_trigger.enabled = False
        self.login_trigger.save()
        self.assertEqual(self.fire().deliveries.filter(status='skipped').count(), 3)
    def test_consent_and_missing_recipient(self):
        self.profile.email_consent = False
        self.profile.phone = ''
        self.profile.save()
        self.user.push_subscriptions.all().delete()
        self.assertEqual(self.fire().deliveries.filter(status='skipped').count(), 3)
    def test_duplicate_event_does_not_resend(self):
        first = self.fire(key='unique-event')
        second = self.fire(key='unique-event')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Delivery.objects.count(), 3)
    def test_claimed_delivery_is_not_sent_twice(self):
        event = self.fire()
        with patch('notifications.services.send') as send:
            dispatch(event.deliveries.first().pk)
            send.assert_not_called()
    def test_channel_failure_does_not_block_other_channels(self):
        def sender(delivery):
            if delivery.channel == 'email':
                raise ProviderError('Email failure')
            return 'accepted', 'provider-id', 'Accepted'
        with patch('notifications.services.send', side_effect=sender):
            event = self.fire()
        self.assertEqual(event.deliveries.get(channel='email').status, 'failed')
        self.assertEqual(event.deliveries.filter(status='accepted').count(), 2)
    def test_mappings_render_and_preserve_snapshot(self):
        event = self.fire()
        delivery = event.deliveries.get(channel='email')
        self.assertIn('nikhil', delivery.snapshot['body'])
        self.email.body = 'Changed after send'
        self.email.save()
        delivery.refresh_from_db()
        self.assertNotEqual(delivery.snapshot['body'], self.email.body)
    def test_non_admin_cannot_manage_or_test_templates(self):
        self.user.is_staff = False
        self.user.save()
        for path, method in [('/api/triggers/', 'get'), ('/api/templates/', 'get'), (f'/api/templates/{self.email.pk}/test/', 'post')]:
            self.assertEqual(getattr(self.client, method)(path).status_code, 403)
    def test_anonymous_cannot_access_admin(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/triggers/').status_code, 401)
    def test_rejects_unmapped_and_unsafe_variables(self):
        for changes in [{'body': 'Hi {{unknown}}'}, {'body': 'Hi {{name}}', 'variable_mappings': {'name': 'user.password'}}, {'body': 'Hi {{broken'}]:
            response = self.client.patch(f'/api/templates/{self.email.pk}/', changes, format='json')
            self.assertEqual(response.status_code, 400, response.data)
    def test_unique_template_per_trigger_channel(self):
        response = self.client.post('/api/templates/', {'trigger': self.login_trigger.pk, 'channel': 'email', 'title': 'Duplicate', 'body': 'Hello'}, format='json')
        self.assertEqual(response.status_code, 400)
    def test_edit_resets_whatsapp_approval(self):
        template = self.login_trigger.templates.get(channel='whatsapp')
        template.provider_name = 'approved_v1'
        template.provider_status = 'APPROVED'
        template.save()
        response = self.client.patch(f'/api/templates/{template.pk}/', {'body': 'Hello {{name}}, this is your new login message.'}, format='json')
        self.assertEqual(response.status_code, 200)
        template.refresh_from_db()
        self.assertEqual(template.provider_status, 'DRAFT')
        self.assertEqual(template.provider_name, '')
        self.assertEqual(template.revision, 2)
    def test_toggle_preserves_whatsapp_approval(self):
        template = self.login_trigger.templates.get(channel='whatsapp')
        template.provider_status = 'APPROVED'
        template.save()
        self.client.patch(f'/api/templates/{template.pk}/', {'enabled': False}, format='json')
        template.refresh_from_db()
        self.assertEqual(template.provider_status, 'APPROVED')
        self.assertEqual(template.revision, 1)
    def test_dry_sync_never_fakes_approval(self):
        template = self.login_trigger.templates.get(channel='whatsapp')
        response = self.client.post(f'/api/templates/{template.pk}/sync/')
        self.assertEqual(response.data['provider_status'], 'DRAFT')
    def test_login_logout_fire_and_revoke_token(self):
        self.client.force_authenticate(user=None)
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.post('/api/auth/login/', {'username': 'nikhil', 'password': 'Strong-test-pass-472!'}, format='json')
        self.assertEqual(result.status_code, 200)
        token = result.data['token']
        self.assertEqual(NotificationEvent.objects.filter(trigger_key='login').count(), 1)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.post('/api/auth/logout/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(NotificationEvent.objects.filter(trigger_key='logout').count(), 1)
        self.assertEqual(Delivery.objects.count(), 6)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
    def test_expired_token_rejected(self):
        token = Token.objects.create(user=self.user)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=13))
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
    def test_invalid_login_does_not_fire(self):
        self.client.force_authenticate(user=None)
        result = self.client.post('/api/auth/login/', {'username': 'nikhil', 'password': 'incorrect'}, format='json')
        self.assertEqual(result.status_code, 401)
        self.assertFalse(NotificationEvent.objects.exists())
    def test_test_send_respects_disabled_channel(self):
        self.email.enabled = False
        self.email.save()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/templates/{self.email.pk}/test/')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Delivery.objects.get().status, 'skipped')
    def test_custom_event_requires_idempotency_key(self):
        trigger = Trigger.objects.create(key='order_placed', name='Order placed')
        path = f'/api/triggers/{trigger.pk}/fire/'
        self.assertEqual(self.client.post(path).status_code, 400)
        key = str(uuid.uuid4())
        first = self.client.post(path, HTTP_IDEMPOTENCY_KEY=key)
        second = self.client.post(path, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.data['event_id'], second.data['event_id'])
    def test_auth_events_cannot_be_fired_from_admin_demo(self):
        self.assertEqual(self.client.post(f'/api/triggers/{self.login_trigger.pk}/fire/').status_code, 400)
    def test_subscription_cannot_be_stolen(self):
        other = get_user_model().objects.create_user('other')
        self.client.force_authenticate(other)
        response = self.client.post('/api/push-subscriptions/', {'subscription_id': str(self.subscription.subscription_id)}, format='json')
        self.assertEqual(response.status_code, 409)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.user_id, self.user.pk)
    def test_user_only_sees_own_delivery_logs(self):
        self.fire()
        other = get_user_model().objects.create_user('other')
        self.client.force_authenticate(other)
        response = self.client.get('/api/deliveries/')
        self.assertEqual(response.data['count'], 0)
    def test_recipient_masked_and_snapshot_not_exposed(self):
        self.fire()
        response = self.client.get('/api/deliveries/')
        email_log = next(d for d in response.data['results'] if d['channel'] == 'email')
        self.assertEqual(email_log['recipient'], 'n***@example.com')
        self.assertNotIn('snapshot', email_log)
    def test_seed_is_idempotent_and_preserves_edits(self):
        self.email.body = 'Edited content'
        self.email.save()
        call_command('seed_demo', verbosity=0)
        self.email.refresh_from_db()
        self.assertEqual(self.email.body, 'Edited content')
        self.assertEqual(NotificationTemplate.objects.count(), 6)
    def test_profile_rejects_invalid_phone(self):
        response = self.client.patch('/api/auth/me/', {'phone': '123'}, format='json')
        self.assertEqual(response.status_code, 400)
    def test_configuration_does_not_expose_keys(self):
        response = self.client.get('/api/config/')
        self.assertEqual(set(response.data), {'dry_run', 'inline', 'onesignal_app_id', 'providers'})

    @override_settings(NOTIFICATIONS_INLINE=False)
    def test_queued_dry_run_remains_simulated_after_mode_change(self):
        event = self.fire()
        delivery = event.deliveries.get(channel='email')
        self.assertEqual(delivery.status, 'queued')
        with self.settings(NOTIFICATIONS_DRY_RUN=False):
            with patch('notifications.providers.requests.request') as http:
                dispatch(delivery.pk)
                http.assert_not_called()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'simulated')

    def test_concurrent_edit_revalidates_locked_template(self):
        from notifications.serializers import TemplateSerializer
        from rest_framework.exceptions import ValidationError
        serializer = TemplateSerializer(self.email, data={'body': 'Hi {{name}}, updated.'}, partial=True)
        self.assertTrue(serializer.is_valid())
        NotificationTemplate.objects.filter(pk=self.email.pk).update(body='No variables here', variable_mappings={})
        with self.assertRaises(ValidationError):
            serializer.save()
