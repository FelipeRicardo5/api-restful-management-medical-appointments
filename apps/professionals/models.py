from django.db import models


class HealthProfessional(models.Model):
    """A health professional (Profissional da Saude)."""

    nome_social = models.CharField(max_length=150)
    profissao = models.CharField(max_length=100)
    endereco = models.CharField(max_length=255)
    contato = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_social"]

    def __str__(self):
        return f"{self.nome_social} ({self.profissao})"
