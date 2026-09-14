from rest_framework import viewsets

from .models import Appointment
from .serializers import AppointmentSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.select_related("profissional").all()
    serializer_class = AppointmentSerializer
    filterset_fields = ["profissional"]
