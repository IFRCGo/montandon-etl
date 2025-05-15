from rest_framework import serializers

from apps.etl.models import EtlTrace, ExtractionData


class RetriggerSerializer(serializers.ModelSerializer):
    trace_id = serializers.IntegerField(required=True)

    class Meta:
        model = ExtractionData
        fields = ["trace_id"]

    def validate(self, attrs):
        """
        Ensure that trace_id is provided.
        """
        trace_id = attrs.get("trace_id")

        if not trace_id:
            raise serializers.ValidationError("The 'trace_id' field is required.")

        if not EtlTrace.objects.filter(id=trace_id).exists():
            raise serializers.ValidationError(f"trace_id {trace_id} does not exist.")

        return attrs

    def return_id(self):
        return []

    # Note: Handler here
    # def retrigger_logic(self):
    #     # Get the trace_id from validated data
    #     trace_id_value = self.validated_data.get('trace_id')

    #     # Look up the ExtractionData instance based on trace_id and failed status
    #     instance = ExtractionData.objects.filter(
    #         trace__trace_id=trace_id_value,  # Using trace_id from EtlTrace
    #         status='failed'
    #     ).first()

    #     if instance:
    #         # Apply retrigger logic
    #         success = your_extraction_function(instance)  # Perform extraction logic
    #         instance.status = "success" if success else "failed"
    #         instance.save()
    #         return instance
    #     else:
    #         raise serializers.ValidationError("No failed ExtractionData found with the provided trace_id.")
