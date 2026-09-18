from rest_framework import serializers

from .models import HealthProfessional


class HealthProfessionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthProfessional
        fields = [
            "id",
            "nome_social",
            "profissao",
            "endereco",
            "contato",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
