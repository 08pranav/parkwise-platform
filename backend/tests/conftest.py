import pytest
from rest_framework.test import APIClient

from .factories import GuardFactory, SlotFactory, SocietyFactory, UserFactory, VehicleFactory


@pytest.fixture
def society(db):
    return SocietyFactory()


@pytest.fixture
def user(db, society):
    return UserFactory(society=society)


@pytest.fixture
def vehicle(user):
    return VehicleFactory(user=user)


@pytest.fixture
def slot(society):
    return SlotFactory(society=society)


@pytest.fixture
def guard(society):
    return GuardFactory(society=society)


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def auth_client():
    def make(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return make
