from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.tickets.selectors import get_active_tickets_of
from apps.tickets.services import TicketConflictError
from apps.users.models import User


def is_company_email(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()

    return domain == settings.COMPANY_EMAIL_DOMAIN.lower()


def register_requester(username: str, email: str, password: str) -> User:
    user = User(username=username, email=email.lower(), role=User.Role.REQUESTER)
    user.set_password(password)
    try:
        # Savepoint: the email unique constraint still protects us if two
        # requests register the same email at the same time.
        with transaction.atomic():
            user.save()
    except IntegrityError as ex:
        raise ValidationError("This email is already in use.") from ex

    return user


def blacklist_all_refresh_tokens(user: User) -> None:
    for token in OutstandingToken.objects.filter(
        user=user, blacklistedtoken__isnull=True
    ):
        BlacklistedToken.objects.get_or_create(token=token)


@transaction.atomic
def change_password(user: User, new_password: str) -> None:
    user.set_password(new_password)
    user.save(update_fields=["password"])
    blacklist_all_refresh_tokens(user)


@transaction.atomic
def grant_it_support_role(user_id) -> User:
    try:
        user = User.objects.select_for_update().get(pk=user_id)
    except (User.DoesNotExist, ValidationError, ValueError, TypeError) as ex:
        raise ObjectDoesNotExist("User not found.") from ex

    if user.role == User.Role.IT_SUPPORT:
        raise ValidationError("This account is already an IT Support.")

    if user.role != User.Role.REQUESTER or not user.is_active:
        raise ValidationError(
            "Only active Requester accounts can be granted the IT Support role."
        )

    user.role = User.Role.IT_SUPPORT
    user.save(update_fields=["role"])

    return user


@transaction.atomic
def deactivate_it_support(user_id) -> User:
    user = User.objects.select_for_update().get(pk=user_id, role=User.Role.IT_SUPPORT)

    active_tickets = list(get_active_tickets_of(user).values_list("title", flat=True))
    if active_tickets:
        raise TicketConflictError(
            "This IT Support still holds PROCESSING or REOPEN tickets. "
            "Transfer them to another IT Support first: " + ", ".join(active_tickets)
        )

    user.is_active = False
    user.save(update_fields=["is_active"])
    blacklist_all_refresh_tokens(user)

    return user
