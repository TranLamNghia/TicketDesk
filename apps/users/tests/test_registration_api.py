import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.tests.factories import UserFactory
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestRegister:
    def test_register_with_company_email_success(self, api_client):
        payload = {
            "username": "an.nguyen",
            "email": "an.nguyen@rainscales.com",
            "password": "Matkhau123",
            "password_confirm": "Matkhau123",
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        user = User.objects.get(username="an.nguyen")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["role"] == User.Role.REQUESTER
        assert "password" not in response.data
        assert user.role == User.Role.REQUESTER
        assert user.check_password("Matkhau123")

    def test_registered_account_can_log_in(self, api_client):
        api_client.post(
            "/api/v1/auth/register/",
            {
                "username": "an.nguyen",
                "email": "an.nguyen@rainscales.com",
                "password": "Matkhau123",
                "password_confirm": "Matkhau123",
            },
        )

        response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "an.nguyen", "password": "Matkhau123"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_register_cannot_choose_another_role(self, api_client):
        payload = {
            "username": "an.nguyen",
            "email": "an.nguyen@rainscales.com",
            "password": "Matkhau123",
            "password_confirm": "Matkhau123",
            "role": User.Role.IT_MANAGER,
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.get(username="an.nguyen").role == User.Role.REQUESTER

    def test_register_with_used_email_fails(self, api_client):
        UserFactory(username="an_cu", email="an.nguyen@rainscales.com")
        payload = {
            "username": "an.nguyen",
            "email": "AN.NGUYEN@rainscales.com",
            "password": "Matkhau123",
            "password_confirm": "Matkhau123",
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data
        assert not User.objects.filter(username="an.nguyen").exists()

    def test_register_with_non_company_email_fails(self, api_client):
        payload = {
            "username": "an.nguyen",
            "email": "an.nguyen@gmail.com",
            "password": "Matkhau123",
            "password_confirm": "Matkhau123",
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data
        assert not User.objects.filter(username="an.nguyen").exists()

    @pytest.mark.parametrize(
        "weak_password",
        ["abc123", "matkhaumoi", "12345678"],
    )
    def test_register_with_weak_password_fails(self, api_client, weak_password):
        payload = {
            "username": "an.nguyen",
            "email": "an.nguyen@rainscales.com",
            "password": weak_password,
            "password_confirm": weak_password,
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data
        assert not User.objects.filter(username="an.nguyen").exists()

    def test_register_with_mismatched_password_confirm_fails(self, api_client):
        payload = {
            "username": "an.nguyen",
            "email": "an.nguyen@rainscales.com",
            "password": "Matkhau123",
            "password_confirm": "Matkhau124",
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password_confirm" in response.data

    def test_register_with_taken_username_fails(self, api_client):
        UserFactory(username="an.nguyen", email="an.khac@rainscales.com")
        payload = {
            "username": "AN.NGUYEN",
            "email": "an.nguyen@rainscales.com",
            "password": "Matkhau123",
            "password_confirm": "Matkhau123",
        }

        response = api_client.post("/api/v1/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.data
