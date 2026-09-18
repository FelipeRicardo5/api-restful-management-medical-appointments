from unittest import mock

from django.contrib.auth import get_user_model
from django.db.utils import OperationalError
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException
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

    def test_rotated_refresh_token_is_blacklisted(self):
        """ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION must actually
        invalidate the old token - it only does if the token_blacklist app is
        installed, so assert the behaviour rather than trusting the setting."""
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "tester", "password": self.password},
        )
        old_refresh = token_response.data["refresh"]

        first = self.client.post(reverse("token_refresh"), {"refresh": old_refresh})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertNotEqual(first.data["refresh"], old_refresh)

        replayed = self.client.post(reverse("token_refresh"), {"refresh": old_refresh})
        self.assertEqual(replayed.status_code, status.HTTP_401_UNAUTHORIZED)


class HealthCheckTests(APITestCase):
    """The probes must answer without a JWT - the ALB has no credentials."""

    def test_liveness_returns_200_without_authentication(self):
        response = self.client.get(reverse("health-live"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})

    def test_readiness_returns_200_when_database_is_reachable(self):
        response = self.client.get(reverse("health-ready"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok", "database": "ok"})

    def test_readiness_returns_503_when_database_is_unreachable(self):
        with mock.patch(
            "apps.core.views.connection.cursor",
            side_effect=OperationalError("connection refused"),
        ):
            response = self.client.get(reverse("health-ready"))

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data, {"status": "error", "database": "error"})


class ExceptionHandlerTests(APITestCase):
    """The custom handler exists so an unhandled exception still returns JSON
    instead of Django's HTML error page - assert that contract directly."""

    def setUp(self):
        self.user = User.objects.create_user(username="handler", password="strongpass123")
        self.client.force_authenticate(user=self.user)

    def test_unhandled_exception_returns_json_500(self):
        with mock.patch(
            "apps.professionals.views.HealthProfessionalViewSet.list",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertLogs("apps.core.exceptions", level="ERROR"):
                response = self.client.get(reverse("professional-list"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.data, {"detail": "Internal server error."})

    def test_drf_5xx_response_is_logged(self):
        with mock.patch(
            "apps.professionals.views.HealthProfessionalViewSet.list",
            side_effect=APIException("upstream unavailable"),
        ):
            with self.assertLogs("apps.core.exceptions", level="ERROR") as logs:
                response = self.client.get(reverse("professional-list"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertTrue(any("Server error 500" in line for line in logs.output))
