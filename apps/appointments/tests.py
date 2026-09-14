from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.professionals.models import HealthProfessional

from .models import Appointment

User = get_user_model()


class AppointmentCRUDTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="strongpass123")
        self.client.force_authenticate(user=self.user)
        self.professional = HealthProfessional.objects.create(
            nome_social="Alex Souza",
            profissao="Psicologia",
            endereco="Rua das Flores, 100",
            contato="alex@example.com",
        )
        self.other_professional = HealthProfessional.objects.create(
            nome_social="Bruna Reis",
            profissao="Nutricao",
            endereco="Rua das Palmeiras, 50",
            contato="bruna@example.com",
        )
        self.appointment = Appointment.objects.create(
            profissional=self.professional, data=timezone.now() + timedelta(days=1)
        )
        self.list_url = reverse("appointment-list")
        self.detail_url = reverse("appointment-detail", args=[self.appointment.id])

    def test_list_appointments(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_create_appointment(self):
        payload = {
            "profissional": self.professional.id,
            "data": (timezone.now() + timedelta(days=2)).isoformat(),
        }
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_retrieve_appointment(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profissional"], self.professional.id)

    def test_update_appointment(self):
        new_date = timezone.now() + timedelta(days=5)
        response = self.client.patch(self.detail_url, {"data": new_date.isoformat()})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_appointment(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Appointment.objects.filter(id=self.appointment.id).exists())

    def test_retrieve_unknown_appointment_returns_404(self):
        url = reverse("appointment-detail", args=[999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_search_appointments_by_professional_id_via_query_param(self):
        Appointment.objects.create(
            profissional=self.other_professional, data=timezone.now() + timedelta(days=3)
        )
        response = self.client.get(self.list_url, {"profissional": self.professional.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.appointment.id)

    def test_search_appointments_by_professional_id_via_nested_route(self):
        url = reverse("professional-appointments", args=[self.professional.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.appointment.id)


class AppointmentValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="strongpass123")
        self.client.force_authenticate(user=self.user)
        self.professional = HealthProfessional.objects.create(
            nome_social="Alex Souza",
            profissao="Psicologia",
            endereco="Rua das Flores, 100",
            contato="alex@example.com",
        )
        self.list_url = reverse("appointment-list")

    def test_create_missing_fields_returns_400(self):
        response = self.client.post(self.list_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("data", response.data)
        self.assertIn("profissional", response.data)

    def test_create_with_invalid_professional_id_returns_400(self):
        payload = {
            "profissional": 999999,
            "data": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profissional", response.data)

    def test_create_with_past_date_returns_400(self):
        payload = {
            "profissional": self.professional.id,
            "data": (timezone.now() - timedelta(days=1)).isoformat(),
        }
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("data", response.data)


class AppointmentAuthTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("appointment-list")

    def test_list_without_authentication_returns_401(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
