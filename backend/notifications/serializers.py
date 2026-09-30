from django.db import transaction
from rest_framework import serializers
from .models import Trigger, NotificationTemplate, Delivery
from .variables import validate_content

class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'trigger', 'channel', 'title', 'body', 'variable_mappings', 'enabled', 'language', 'category',
                  'revision', 'provider_name', 'provider_status', 'provider_error', 'updated_at']
        read_only_fields = ['revision', 'provider_name', 'provider_status', 'provider_error', 'updated_at']
    def validate(self, attrs):
        current = self.instance
        def value(key, default=''):
            return attrs.get(key, getattr(current, key, default))
        if current and any(k in attrs and attrs[k] != getattr(current, k) for k in ['trigger', 'channel']):
            raise serializers.ValidationError('A template cannot change its trigger or channel.')
        validate_content(value('title'), value('body'), value('variable_mappings', {}), value('channel'))
        return attrs
    def validate_language(self, value):
        import re
        if not re.fullmatch(r'[a-z]{2,3}(?:_[A-Z]{2})?', value):
            raise serializers.ValidationError('Use a language code such as en_US.')
        return value
    @transaction.atomic
    def update(self, instance, validated_data):
        instance = NotificationTemplate.objects.select_for_update().get(pk=instance.pk)
        # Revalidate against the locked row, not the earlier potentially stale read.
        validate_content(validated_data.get('title', instance.title),
                         validated_data.get('body', instance.body),
                         validated_data.get('variable_mappings', instance.variable_mappings), instance.channel)
        content_fields = ['title', 'body', 'variable_mappings', 'language', 'category']
        if any(k in validated_data and validated_data[k] != getattr(instance, k) for k in content_fields):
            instance.revision += 1
            instance.provider_name = ''
            instance.provider_status = 'DRAFT'
            instance.provider_error = ''
        return super().update(instance, validated_data)

class TriggerSerializer(serializers.ModelSerializer):
    templates = TemplateSerializer(many=True, read_only=True)
    class Meta:
        model = Trigger
        fields = ['id', 'key', 'name', 'description', 'enabled', 'templates']
    def validate_key(self, value):
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_]*', value):
            raise serializers.ValidationError('Use lowercase letters, digits and underscores, starting with a letter.')
        if self.instance and self.instance.key != value:
            raise serializers.ValidationError('Trigger keys cannot be changed after creation.')
        return value

class DeliverySerializer(serializers.ModelSerializer):
    trigger = serializers.CharField(source='event.trigger_key', read_only=True)
    is_test = serializers.BooleanField(source='event.is_test', read_only=True)
    username = serializers.CharField(source='event.user.username', read_only=True)
    recipient = serializers.SerializerMethodField()
    def get_recipient(self, obj):
        if '@' in obj.recipient:
            local, domain = obj.recipient.rsplit('@', 1)
            return local[:1] + '***@' + domain
        return '…' + obj.recipient[-4:] if obj.recipient else ''
    class Meta:
        model = Delivery
        fields = ['id', 'trigger', 'channel', 'status', 'recipient', 'provider_message_id', 'detail', 'created_at', 'is_test', 'username']
