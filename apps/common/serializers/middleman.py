from rest_framework import serializers


class AuditModelSerializerMixin(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    def get_created_by(self, obj):
        return self.context['request'].user.username

    def get_updated_by(self, obj):
        return self.context['request'].user.username
