from django.utils.translation import get_language

from offgridplanner.users.models import User


def test_user_get_absolute_url(user: User):
    assert user.get_absolute_url() == f"/{get_language()}/users/{user.pk}/"
