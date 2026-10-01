import uuid
from types import SimpleNamespace
from unittest.mock import patch, Mock
import requests
from django.test import SimpleTestCase, override_settings
from notifications.providers import api, send, sync_whatsapp, ProviderError
from notifications.variables import whatsapp_body

@override_settings(WHATSAPP_DRY_RUN=False, NOTIFICATIONS_DRY_RUN=False, WHATSAPP_ACCESS_TOKEN='test-token', PHONE_NUMBER_ID='test-phone-id',
    WHATSAPP_BUSINESS_ACCOUNT_ID='test-business', POSTMARKAPP_TOKEN='postmark-test', POSTMARK_FROM_EMAIL='sender@example.com',
    ONESIGNAL_APP_ID='test-app', ONESIGNAL_REST_API_KEY='test-key', SANDBOX_EMAILS=['test@example.com'], SANDBOX_PHONES=['+919876543210'])
class ProviderTests(SimpleTestCase):
    def delivery(self, channel, recipient):
        return SimpleNamespace(pk=uuid.uuid4(), channel=channel, recipient=recipient, snapshot={
            'title': 'Login confirmed', 'body': 'Hello Nikhil', 'provider_status': 'APPROVED',
            'provider_name': 'login_v1', 'parameters': ['Nikhil'], 'language': 'en_US'})
    @patch('notifications.providers.api')
    def test_postmark_payload(self, api_mock):
        api_mock.return_value = {'MessageID': 'mail-1'}
        result = send(self.delivery('email', 'test@example.com'))
        self.assertEqual(result[0], 'accepted')
        payload = api_mock.call_args.args[3]
        self.assertEqual(payload['TextBody'], 'Hello Nikhil')
        self.assertEqual(payload['MessageStream'], 'outbound')
    @patch('notifications.providers.api')
    def test_whatsapp_uses_approved_template_with_ordered_variables(self, api_mock):
        api_mock.return_value = {'messages': [{'id': 'wa-1'}]}
        send(self.delivery('whatsapp', '+919876543210'))
        payload = api_mock.call_args.args[3]
        self.assertEqual(payload['template']['name'], 'login_v1')
        self.assertEqual(payload['template']['components'][0]['parameters'], [{'type': 'text', 'text': 'Nikhil'}])
    @patch('notifications.providers.api')
    def test_whatsapp_rejects_unapproved_template(self, api_mock):
        delivery = self.delivery('whatsapp', '+919876543210')
        delivery.snapshot['provider_status'] = 'PENDING'
        with self.assertRaises(ProviderError):
            send(delivery)
        api_mock.assert_not_called()
    @patch('notifications.providers.api')
    def test_only_allowlisted_recipients(self, api_mock):
        with self.assertRaises(ProviderError):
            send(self.delivery('email', 'someone-else@example.com'))
        api_mock.assert_not_called()
    @patch('notifications.providers.api')
    def test_push_excludes_mobile_and_uses_idempotency(self, api_mock):
        api_mock.return_value = {'id': 'push-1'}
        delivery = self.delivery('push', str(uuid.uuid4()))
        with self.settings(SANDBOX_PUSH_IDS=[delivery.recipient]):
            send(delivery)
        payload = api_mock.call_args.args[3]
        self.assertTrue(payload['isAnyWeb'])
        self.assertFalse(payload['isIos'])
        self.assertFalse(payload['isAndroid'])
        self.assertEqual(payload['include_subscription_ids'], [delivery.recipient])
        self.assertEqual(payload['idempotency_key'], str(delivery.pk))
    @patch('notifications.providers.api', return_value={'id': ''})
    def test_missing_provider_id_not_success(self, api_mock):
        with self.assertRaises(ProviderError):
            send(self.delivery('email', 'test@example.com'))
    @patch('notifications.providers.requests.request', side_effect=requests.Timeout())
    def test_timeout_marks_uncertainty(self, request_mock):
        with self.assertRaisesRegex(ProviderError, 'uncertain'):
            api('POST', 'https://example.com', {})
        self.assertEqual(request_mock.call_count, 1)
    @patch('notifications.providers.requests.request')
    def test_upstream_error_does_not_leak_secrets(self, request_mock):
        request_mock.return_value = Mock(ok=False, status_code=401, json=lambda: {'error': {'message': 'secret token leaked'}})
        with self.assertRaises(ProviderError) as error:
            api('POST', 'https://example.com', {})
        self.assertNotIn('secret token', str(error.exception))
    def test_named_variables_to_numbered_whatsapp_body(self):
        self.assertEqual(whatsapp_body('Hello {{name}}, {{event}} for {{name}}.'), 'Hello {{1}}, {{2}} for {{1}}.')
    @patch('notifications.providers.api', return_value={'status': 'PENDING'})
    def test_sync_creates_template_with_samples(self, api_mock):
        template = SimpleNamespace(pk=1, revision=2, trigger=SimpleNamespace(key='login'), provider_name='',
            body='Hello {{name}}, you logged in.', variable_mappings={'name': 'user.name'}, language='en_US', category='UTILITY')
        name, status, error = sync_whatsapp(template)
        self.assertTrue(name.startswith('sc_login_1_v2_'))
        self.assertEqual(status, 'PENDING')
        self.assertEqual(api_mock.call_args.args[3]['components'][0]['example']['body_text'], [['Nikhil']])
    @patch('notifications.providers.api', return_value={'data': [{'name': 'login_v1', 'language': 'en_US', 'status': 'APPROVED'}]})
    def test_sync_polls_existing_template(self, api_mock):
        template = SimpleNamespace(provider_name='login_v1', language='en_US')
        self.assertEqual(sync_whatsapp(template)[1], 'APPROVED')
        self.assertEqual(api_mock.call_args.args[0], 'GET')

    @override_settings(WHATSAPP_DRY_RUN=True)
    @patch('notifications.providers.api')
    def test_whatsapp_only_dry_run_leaves_email_live(self, api_mock):
        api_mock.return_value = {'MessageID': 'mail-1'}
        self.assertEqual(send(self.delivery('whatsapp', '+919876543210'))[0], 'simulated')
        self.assertEqual(sync_whatsapp(SimpleNamespace())[1], 'DRAFT')
        api_mock.assert_not_called()
        self.assertEqual(send(self.delivery('email', 'test@example.com'))[0], 'accepted')
        self.assertEqual(api_mock.call_count, 1)

    @patch('notifications.providers.requests.request')
    def test_postmark_approval_error_is_actionable_without_private_response(self, request_mock):
        request_mock.return_value = Mock(ok=False, status_code=422, json=lambda: {
            'ErrorCode': 412, 'Message': 'private recipient and token'})
        with self.assertRaises(ProviderError) as error:
            api('POST', 'https://api.postmarkapp.com/email', {})
        self.assertIn('approval pending (412)', str(error.exception))
        self.assertNotIn('private recipient', str(error.exception))
