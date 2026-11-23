from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SerializerMethodField

from apps.users.models import User
from apps.users.services import is_company_email


class ITSupportSerializer(ModelSerializer):
    current_ticket = SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_active", "current_ticket"]
        read_only_fields = fields

    def get_current_ticket(self, obj):
        ticket_id = getattr(obj, "current_ticket_id", None)
        if ticket_id is None:
            return None
        return {"id": str(ticket_id), "title": obj.current_ticket_title}


def _run_password_validators(password, user, field_name):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as ex:
        raise serializers.ValidationError({field_name: list(ex.messages)}) from ex


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150, validators=[UnicodeUsernameValidator()]
    )
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")

        return value

    def validate_email(self, value):
        email = value.lower()
        if not is_company_email(email):
            raise serializers.ValidationError(
                f"Only company emails (@{settings.COMPANY_EMAIL_DOMAIN}) can register."
            )

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("This email is already in use.")

        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": ["Passwords do not match."]}
            )

        _run_password_validators(
            attrs["password"],
            User(username=attrs["username"], email=attrs["email"]),
            "password",
        )

        return attrs


class RegisteredUserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")

        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": ["Passwords do not match."]}
            )

        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {
                    "new_password": [
                        "New password must be different from the current password."
                    ]
                }
            )

        _run_password_validators(
            attrs["new_password"], self.context["request"].user, "new_password"
        )

        return attrs
