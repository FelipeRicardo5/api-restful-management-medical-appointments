import logging

from django.db import connection
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("apps.core.health")


class LivenessView(APIView):
    """Liveness probe: is the process up and serving?

    Deliberately checks no external dependency. This is the endpoint the ALB
    target group points at: if it checked the database, a transient RDS
    failover would mark every task unhealthy and the ALB would drain the whole
    service - turning a recoverable database blip into a full outage.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Liveness probe",
        description="Returns 200 while the process is up. Used by the ALB target group.",
        responses={
            200: OpenApiResponse(
                description="Process is alive",
                examples=[OpenApiExample("ok", value={"status": "ok"})],
            )
        },
    )
    def get(self, request):
        return Response({"status": "ok"})


class ReadinessView(APIView):
    """Readiness probe: can the app actually serve traffic end to end?

    Verifies database connectivity. Used for diagnostics and as a post-deploy
    smoke check - not by the ALB, for the reason described in LivenessView.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Readiness probe",
        description="Returns 200 when the database is reachable, 503 otherwise.",
        responses={
            200: OpenApiResponse(
                description="All dependencies reachable",
                examples=[OpenApiExample("ready", value={"status": "ok", "database": "ok"})],
            ),
            503: OpenApiResponse(
                description="A dependency is unreachable",
                examples=[
                    OpenApiExample("not ready", value={"status": "error", "database": "error"})
                ],
            ),
        },
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            logger.exception("Readiness check failed: database unreachable")
            return Response(
                {"status": "error", "database": "error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ok", "database": "ok"})
