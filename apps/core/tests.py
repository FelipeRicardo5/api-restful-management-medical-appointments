from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class JWTAuthFlowTests(APITestCase):
    def setUp(self):
        self.password = "strongpass123"
        self.user = User.objects.create_user(username="tester", password=self.password)
        self.protected_url = reverse("professional-list")

    def test_obtain_token_with_valid_credentials(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "tester", "password": self.password},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_obtain_token_with_invalid_credentials_returns_401(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "tester", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_protected_endpoint_with_valid_token(self):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "tester", "password": self.password},
        )
        access = token_response.data["access"]
        response = self.client.get(self.protected_url, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_access_protected_endpoint_without_token_returns_401(self):
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_protected_endpoint_with_invalid_token_returns_401(self):
        response = self.client.get(self.protected_url, HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_returns_new_access_token(self):
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "tester", "password": self.password},
        )
        refresh = token_response.data["refresh"]
        response = self.client.post(reverse("token_refresh"), {"refresh": refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
