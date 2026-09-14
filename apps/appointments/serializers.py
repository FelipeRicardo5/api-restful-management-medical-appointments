from django.utils import timezone
from rest_framework import serializers

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["id", "data", "profissional", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_data(self, value):
        is_create = self.instance is None
        if is_create and value < timezone.now():
            raise serializers.ValidationError("A data da consulta nao pode estar no passado.")
        return value
