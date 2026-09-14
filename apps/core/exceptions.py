import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("apps.core.exceptions")


def custom_exception_handler(exc, context):
    """Wraps DRF's default handler: guarantees a JSON body even for
    unhandled exceptions (DRF returns None for those, which would otherwise
    fall through to Django's HTML error page) and logs every 5xx."""
    response = exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled exception in %s", context["view"], exc_info=exc)
        return Response(
            {"detail": "Internal server error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if response.status_code >= 500:
        logger.error("Server error %s: %s", response.status_code, response.data)

    return response
