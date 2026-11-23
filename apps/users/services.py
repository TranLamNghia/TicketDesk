from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

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
