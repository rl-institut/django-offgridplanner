from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from offgridplanner.users.models import User

UserModel = get_user_model()


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.request.user.pk})


user_redirect_view = UserRedirectView.as_view()


@login_required
@require_http_methods(["POST"])
def convert_demo_account(request):
    user = request.user

    email = request.POST["email"].strip().lower()
    password = request.POST["password"]

    user_qs = User.objects.filter(email=email)
    if not hasattr(user, "demo") or user_qs.exists():
        # Account is already a real user account
        msg = "User account already exists"
        messages.add_message(request, messages.INFO, msg)
        return redirect("projects:projects_list")

    user.email = email
    user.set_password(password)
    user.save()

    # Remove demo marker
    user.demo.delete()

    # Update hash to keep user logged in
    update_session_auth_hash(request, user)
    msg = "User account successfully created"
    messages.add_message(request, messages.INFO, msg)

    return redirect("projects:projects_list")
