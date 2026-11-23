import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestChangePassword:
    def test_change_password_success(self, api_client):
        user = UserFactory(username="requester01", password="Matkhau123")

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "Matkhau123",
                "new_password": "Matkhaumoi456",
                "new_password_confirm": "Matkhaumoi456",
            },
        )

        user.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["detail"] == "Password changed successfully."
        assert user.check_password("Matkhaumoi456")
        assert not user.check_password("Matkhau123")

    def test_change_password_with_wrong_current_password_fails(self, api_client):
        user = UserFactory(username="requester01", password="Matkhau123")

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "SaiMatKhau999",
                "new_password": "Matkhaumoi456",
                "new_password_confirm": "Matkhaumoi456",
            },
        )

        user.refresh_from_db()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "current_password" in response.data
        assert user.check_password("Matkhau123")

    def test_change_password_with_mismatched_confirm_fails(self, api_client):
        user = UserFactory(username="requester01", password="Matkhau123")

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "Matkhau123",
                "new_password": "Matkhaumoi456",
                "new_password_confirm": "Matkhaumoi789",
            },
        )

        user.refresh_from_db()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_password_confirm" in response.data
        assert user.check_password("Matkhau123")

    def test_new_password_same_as_current_fails(self, api_client):
        user = UserFactory(username="requester01", password="Matkhau123")

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "Matkhau123",
                "new_password": "Matkhau123",
                "new_password_confirm": "Matkhau123",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_password" in response.data

    def test_change_password_with_weak_new_password_fails(self, api_client):
        user = UserFactory(username="requester01", password="Matkhau123")

        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "Matkhau123",
                "new_password": "abc123",
                "new_password_confirm": "abc123",
            },
        )

        user.refresh_from_db()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_password" in response.data
        assert user.check_password("Matkhau123")

    def test_change_password_revokes_existing_refresh_tokens(self, api_client):
        UserFactory(username="requester01", password="Matkhau123")
        tokens = api_client.post(
            "/api/v1/auth/token/",
            {"username": "requester01", "password": "Matkhau123"},
        ).data

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "Matkhau123",
                "new_password": "Matkhaumoi456",
                "new_password_confirm": "Matkhaumoi456",
            },
        )
        api_client.credentials()
        response = api_client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_password_requires_authentication(self, api_client):
        response = api_client.post(
            "/api/v1/auth/password/change/",
            {
                "current_password": "Matkhau123",
                "new_password": "Matkhaumoi456",
                "new_password_confirm": "Matkhaumoi456",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
