from rest_framework import serializers

class ConfigSerializer(serializers.Serializer):
    tenant_id = serializers.CharField(required=False)
    outlook_client_id = serializers.CharField(required=False)
    outlook_client_secret = serializers.CharField(required=False)

class StartEmailExtractionSerializer(serializers.Serializer):
    config = ConfigSerializer()
    user_upn = serializers.EmailField()

class EmailExtractionStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    started_at = serializers.FloatField(required=False)
    completed_at = serializers.FloatField(required=False)
    error = serializers.CharField(required=False, allow_null=True)

class EmailExtractionResultSerializer(serializers.Serializer):
    connection_id = serializers.CharField()
    emails = serializers.ListField(child=serializers.DictField(), required=False)

class StartBatchEmailExtractionSerializer(serializers.Serializer):
    config = ConfigSerializer()
    user_upns = serializers.ListField(
        child=serializers.EmailField(),
        help_text="List of user principal names (emails) to extract in batch."
    )

class BatchEmailExtractionStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    started_at = serializers.FloatField(required=False)
    completed_at = serializers.FloatField(required=False)
    error = serializers.CharField(required=False, allow_null=True)
    total_users = serializers.IntegerField()
    processed_users = serializers.IntegerField()
    failed_users = serializers.IntegerField()
    remaining_users = serializers.IntegerField()

class BatchEmailExtractionResultSerializer(serializers.Serializer):
    batch_id = serializers.CharField()
    processed_users = serializers.ListField(child=serializers.EmailField())
    failed_users = serializers.ListField(child=serializers.EmailField())
    started_at = serializers.FloatField()
    completed_at = serializers.FloatField()

class PauseEmailExtractionSerializer(serializers.Serializer):
    pass

class ContinueEmailExtractionSerializer(serializers.Serializer):
    pass

class CancelEmailExtractionSerializer(serializers.Serializer):
    pass

class PauseBatchEmailExtractionSerializer(serializers.Serializer):
    pass

class ContinueBatchEmailExtractionSerializer(serializers.Serializer):
    pass

class CancelBatchEmailExtractionSerializer(serializers.Serializer):
    pass 