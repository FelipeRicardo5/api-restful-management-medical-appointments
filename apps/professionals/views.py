from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import HealthProfessional
from .serializers import HealthProfessionalSerializer


class HealthProfessionalViewSet(viewsets.ModelViewSet):
    queryset = HealthProfessional.objects.all()
    serializer_class = HealthProfessionalSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "Nao e possivel excluir este profissional: existem "
                        "consultas vinculadas a ele."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=True, methods=["get"], url_path="appointments")
    def appointments(self, request, pk=None):
        """Busca de consultas pelo ID do profissional."""
        from apps.appointments.serializers import AppointmentSerializer

        professional = self.get_object()
        queryset = professional.appointments.all()
        page = self.paginate_queryset(queryset)
        serializer = AppointmentSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
