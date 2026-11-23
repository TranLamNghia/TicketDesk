import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.tests.factories import UserFactory
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestLogin:
    def test_login_with_correct_password_returns_tokens(self, api_client):
        UserFactory(username="requester01", password="Matkhau123")

        response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "requester01", "password": "Matkhau123"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_it_support_login_returns_tokens(self, api_client):
        UserFactory(
            username="itsupport01", password="Matkhau123", role=User.Role.IT_SUPPORT
        )

        response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "itsupport01", "password": "Matkhau123"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_access_token_can_call_protected_api(self, api_client):
        UserFactory(
            username="itsupport01", password="Matkhau123", role=User.Role.IT_SUPPORT
        )
        token_response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "itsupport01", "password": "Matkhau123"},
        )

        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}"
        )
        response = api_client.get("/api/v1/tickets/")

        assert response.status_code == status.HTTP_200_OK

    def test_login_with_wrong_password_fails(self, api_client):
        UserFactory(username="requester01", password="Matkhau123")

        response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "requester01", "password": "SaiMatKhau999"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data

    def test_deactivated_account_cannot_login(self, api_client):
        UserFactory(
            username="itsupport02",
            password="Matkhau123",
            role=User.Role.IT_SUPPORT,
            is_active=False,
        )

        response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "itsupport02", "password": "Matkhau123"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data
