import uuid
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import connection, transaction, IntegrityError
from rest_framework import serializers, status, viewsets, mixins
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from .models import Trigger, NotificationTemplate, Delivery, Profile, PushSubscription
from .serializers import TriggerSerializer, TemplateSerializer, DeliverySerializer
from .providers import sync_whatsapp, ProviderError
from .services import fire_event

class LoginThrottle(AnonRateThrottle):
    scope = 'login'
class SendThrottle(UserRateThrottle):
    scope = 'send'

def user_data(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return {'id': user.pk, 'username': user.username, 'first_name': user.first_name, 'email': user.email,
            'is_staff': user.is_staff, 'phone': profile.phone, 'email_consent': profile.email_consent,
            'whatsapp_consent': profile.whatsapp_consent,
            'push_subscriptions': list(user.push_subscriptions.values_list('subscription_id', flat=True))}

def event_data(event):
    return {'event_id': event.pk, 'deliveries': DeliverySerializer(event.deliveries.all(), many=True).data}

class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)

class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginThrottle]
    def post(self, request):
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(request, **data.validated_data)
        if not user:
            return Response({'detail': 'Invalid username or password.'}, status=401)
        # Rotate the single active token; logout always revokes this session.
        with transaction.atomic():
            type(user).objects.select_for_update().get(pk=user.pk)
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)
            event = fire_event('login', user, f'login:{uuid.uuid4()}')
        return Response({'token': token.key, 'user': user_data(user), **event_data(event)})

class LogoutView(APIView):
    def post(self, request):
        # Token deletion and event persistence commit together before provider calls.
        with transaction.atomic():
            locked = Token.objects.select_for_update().filter(pk=request.auth.pk).first()
            if not locked:
                return Response({'detail': 'Session already closed.'}, status=401)
            event = fire_event('logout', request.user, f'logout:{uuid.uuid4()}')
            locked.delete()
        return Response({'detail': 'Logged out.', **event_data(event)})

class ProfileInput(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.RegexField(r'^\+[1-9]\d{7,14}$', allow_blank=True, required=False)
    email_consent = serializers.BooleanField(required=False)
    whatsapp_consent = serializers.BooleanField(required=False)

class MeView(APIView):
    def get(self, request):
        return Response(user_data(request.user))
    @transaction.atomic
    def patch(self, request):
        data = ProfileInput(data=request.data)
        data.is_valid(raise_exception=True)
        profile, _ = Profile.objects.get_or_create(user=request.user)
        for key, value in data.validated_data.items():
            setattr(request.user if key in ['first_name', 'email'] else profile, key, value)
        request.user.save(update_fields=['first_name', 'email'])
        profile.save()
        return Response(user_data(request.user))

class PushInput(serializers.Serializer):
    subscription_id = serializers.UUIDField()

class PushView(APIView):
    def post(self, request):
        data = PushInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                subscription, _ = PushSubscription.objects.get_or_create(subscription_id=data.validated_data['subscription_id'], defaults={'user': request.user})
        except IntegrityError:
            return Response({'detail': 'Subscription could not be registered.'}, status=409)
        if subscription.user_id != request.user.pk:
            return Response({'detail': 'This browser is associated with another account. Unsubscribe from that account first.'}, status=409)
        return Response({'subscription_id': subscription.subscription_id}, status=201)
    def delete(self, request):
        data = PushInput(data=request.data)
        data.is_valid(raise_exception=True)
        PushSubscription.objects.filter(user=request.user, subscription_id=data.validated_data['subscription_id']).delete()
        return Response(status=204)

class TriggerViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]
    queryset = Trigger.objects.prefetch_related('templates').all()
    serializer_class = TriggerSerializer
    pagination_class = None
    @action(detail=True, methods=['post'], throttle_classes=[SendThrottle])
    def fire(self, request, pk=None):
        trigger = self.get_object()
        # Auth lifecycle events may only be generated by their real endpoints.
        if trigger.key in ['login', 'logout']:
            return Response({'detail': 'Use the website login/logout action for this trigger.'}, status=400)
        key = request.headers.get('Idempotency-Key', '')
        try:
            key = str(uuid.UUID(key))
        except ValueError:
            return Response({'detail': 'Supply an Idempotency-Key UUID header.'}, status=400)
        event = fire_event(trigger.key, request.user, f'custom:{request.user.pk}:{trigger.pk}:{key}')
        return Response(event_data(event))

class TemplateViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]
    queryset = NotificationTemplate.objects.select_related('trigger').all()
    serializer_class = TemplateSerializer
    @action(detail=True, methods=['post'], throttle_classes=[SendThrottle])
    def sync(self, request, pk=None):
        with transaction.atomic():
            template = NotificationTemplate.objects.select_for_update().get(pk=self.get_object().pk)
            if template.channel != 'whatsapp':
                return Response({'detail': 'Only WhatsApp templates require provider approval.'}, status=400)
            try:
                template.provider_name, template.provider_status, template.provider_error = sync_whatsapp(template)
            except ProviderError as exc:
                template.provider_error = str(exc)
                template.save(update_fields=['provider_error', 'updated_at'])
                return Response({'detail': str(exc)}, status=502)
            template.save(update_fields=['provider_name', 'provider_status', 'provider_error', 'updated_at'])
        return Response(self.get_serializer(template).data)
    @action(detail=True, methods=['post'], throttle_classes=[SendThrottle])
    def test(self, request, pk=None):
        template = self.get_object()
        event = fire_event(template.trigger.key, request.user, f'test:{uuid.uuid4()}', test_template=template)
        return Response(event_data(event), status=201)

class DeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliverySerializer
    def get_queryset(self):
        qs = Delivery.objects.select_related('event').all()
        if not self.request.user.is_staff:
            qs = qs.filter(event__user=self.request.user)
        for key in ['status', 'channel']:
            if self.request.query_params.get(key):
                qs = qs.filter(**{key: self.request.query_params[key]})
        return qs

@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return Response({'status': 'unavailable'}, status=503)
    return Response({'status': 'ok'})

@api_view(['GET'])
def configuration(request):
    return Response({'dry_run': settings.NOTIFICATIONS_DRY_RUN, 'inline': settings.NOTIFICATIONS_INLINE,
        'onesignal_app_id': settings.ONESIGNAL_APP_ID,
        'providers': {'whatsapp': bool(settings.WHATSAPP_ACCESS_TOKEN and settings.PHONE_NUMBER_ID and settings.WHATSAPP_BUSINESS_ACCOUNT_ID),
                      'email': bool(settings.POSTMARKAPP_TOKEN and settings.POSTMARK_FROM_EMAIL),
                      'push': bool(settings.ONESIGNAL_APP_ID and settings.ONESIGNAL_REST_API_KEY)}})
