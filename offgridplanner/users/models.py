from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from config.settings.base import AUTH_USER_MODEL

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for Offgridplanner-Django.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = models.EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})


class DemoAccount(models.Model):
    user = models.OneToOneField(
        AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="demo"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    def __str__(self):
        return f"Anonymous user {self.user.email}"
