from django.urls import resolve
from django.urls import reverse
from django.utils.translation import get_language

from offgridplanner.users.models import User


def test_detail(user: User):
    assert (
        reverse("users:detail", kwargs={"pk": user.pk})
        == f"/{get_language()}/users/{user.pk}/"
    )
    assert resolve(f"/{get_language()}/users/{user.pk}/").view_name == "users:detail"


def test_update():
    assert reverse("users:update") == f"/{get_language()}/users/~update/"
    assert resolve(f"/{get_language()}/users/~update/").view_name == "users:update"


def test_redirect():
    assert reverse("users:redirect") == f"/{get_language()}/users/~redirect/"
    assert resolve(f"/{get_language()}/users/~redirect/").view_name == "users:redirect"
