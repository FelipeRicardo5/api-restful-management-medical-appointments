from rest_framework.routers import DefaultRouter

from .views import HealthProfessionalViewSet

router = DefaultRouter()
router.register("professionals", HealthProfessionalViewSet, basename="professional")

urlpatterns = router.urls
