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

    def validate_nome_social(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Nome social nao pode ser vazio.")
        return value

    def validate_profissao(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Profissao nao pode ser vazia.")
        return value

    def validate_contato(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Contato nao pode ser vazio.")
        return value
