from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from apps.tickets.services import TicketConflictError


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid request."
    default_code = "bad_request"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the ticket."
    default_code = "conflict"


def _message_of(ex) -> str:
    if isinstance(ex, DjangoValidationError):
        return ex.messages[0] if ex.messages else str(ex)
    return str(ex)


def to_api_exception(ex) -> APIException:
    """
    Translate exceptions raised by the service layer into DRF exceptions:
    - TicketConflictError     -> 409 Conflict
    - Django PermissionDenied -> 403 Forbidden
    - Django ValidationError / ValueError -> 400 Bad Request
    The response body keeps the existing shape: {"detail": "<message>"}.
    """
    message = _message_of(ex)

    if isinstance(ex, TicketConflictError):
        return Conflict(message)
    if isinstance(ex, DjangoPermissionDenied):
        return PermissionDenied(message or None)
    return BadRequest(message)


SERVICE_EXCEPTIONS = (DjangoValidationError, DjangoPermissionDenied, ValueError)
