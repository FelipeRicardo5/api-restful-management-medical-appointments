from django.contrib import admin

from .models import HealthProfessional


@admin.register(HealthProfessional)
class HealthProfessionalAdmin(admin.ModelAdmin):
    list_display = ("id", "nome_social", "profissao", "contato")
    search_fields = ("nome_social", "profissao")
