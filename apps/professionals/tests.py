from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.appointments.models import Appointment

from .models import HealthProfessional

User = get_user_model()


class HealthProfessionalCRUDTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="strongpass123")
        self.client.force_authenticate(user=self.user)
        self.professional = HealthProfessional.objects.create(
            nome_social="Alex Souza",
            profissao="Psicologia",
            endereco="Rua das Flores, 100",
            contato="alex@example.com",
        )
        self.list_url = reverse("professional-list")
        self.detail_url = reverse("professional-detail", args=[self.professional.id])

    def test_list_professionals(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_create_professional(self):
        payload = {
            "nome_social": "Jordan Lima",
            "profissao": "Clinico Geral",
            "endereco": "Av. Central, 200",
            "contato": "jordan@example.com",
        }
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(HealthProfessional.objects.count(), 2)
        self.assertEqual(response.data["nome_social"], "Jordan Lima")

    def test_retrieve_professional(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nome_social"], "Alex Souza")

    def test_update_professional(self):
        response = self.client.patch(self.detail_url, {"profissao": "Psiquiatria"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.professional.refresh_from_db()
        self.assertEqual(self.professional.profissao, "Psiquiatria")

    def test_delete_professional_without_appointments(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(HealthProfessional.objects.filter(id=self.professional.id).exists())

    def test_delete_professional_with_appointments_is_blocked(self):
        Appointment.objects.create(
            profissional=self.professional, data=timezone.now() + timedelta(days=1)
        )
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(HealthProfessional.objects.filter(id=self.professional.id).exists())

    def test_retrieve_unknown_professional_returns_404(self):
        url = reverse("professional-detail", args=[999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class HealthProfessionalValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="strongpass123")
        self.client.force_authenticate(user=self.user)
        self.list_url = reverse("professional-list")

    def test_create_missing_required_fields_returns_400(self):
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ("nome_social", "profissao", "endereco", "contato"):
            self.assertIn(field, response.data)

    def _post_with(self, **overrides):
        payload = {
            "nome_social": "Alex Souza",
            "profissao": "Enfermagem",
            "endereco": "Rua 1",
            "contato": "x@example.com",
        }
        return self.client.post(self.list_url, {**payload, **overrides})

    def test_create_blank_nome_social_returns_400(self):
        response = self._post_with(nome_social="   ")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nome_social", response.data)

    def test_create_blank_profissao_returns_400(self):
        response = self._post_with(profissao="   ")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profissao", response.data)

    def test_create_blank_contato_returns_400(self):
        response = self._post_with(contato="   ")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contato", response.data)

    def test_surrounding_whitespace_is_stripped_on_create(self):
        response = self._post_with(nome_social="  Jordan Lima  ", profissao="  Clinico  ")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["nome_social"], "Jordan Lima")
        self.assertEqual(response.data["profissao"], "Clinico")


class HealthProfessionalAuthTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("professional-list")

    def test_list_without_authentication_returns_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class HealthProfessionalModelTests(APITestCase):
    def test_str_representation(self):
        professional = HealthProfessional.objects.create(
            nome_social="Alex Souza",
            profissao="Psicologia",
            endereco="Rua das Flores, 100",
            contato="alex@example.com",
        )
        self.assertEqual(str(professional), "Alex Souza (Psicologia)")
