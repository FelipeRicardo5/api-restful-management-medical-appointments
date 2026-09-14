from django.db import models

from apps.professionals.models import HealthProfessional


class Appointment(models.Model):
    """A medical appointment (Consulta) linked to a health professional."""

    data = models.DateTimeField()
    profissional = models.ForeignKey(
        HealthProfessional,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data"]

    def __str__(self):
        return f"{self.profissional} - {self.data}"
