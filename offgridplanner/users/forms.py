from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth import forms as admin_forms
from django.forms import BooleanField
from django.forms import CharField
from django.forms import EmailField
from django.forms import TextInput
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import User


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    # class UserSignupForm(admin_forms.UserCreationForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """

    email = CharField(
        required=True,
        widget=TextInput(attrs={"placeholder": "name@example.com"}),
    )

    accept_privacy = BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        privacy_url = kwargs.pop("privacy_url", "")
        super().__init__(*args, **kwargs)
        self.fields["accept_privacy"].label = mark_safe(  # noqa: S308
            _(
                "I have read and accept the <a target='_blank' href='%(privacy_url)s'>privacy statement</a> from OffgridPlanner",
            )
            % {"privacy_url": privacy_url}
        )

    def save(self, request):
        # Ensure you call the parent class's save.
        # .save() returns a User object.
        user = super().save(request)

        # Add your own processing here.

        # You must return the original result.
        return user

    class Meta:
        model = User
        fields = ("email",)


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """


class CaptchaForm(forms.Form):
    captcha = CaptchaField()
