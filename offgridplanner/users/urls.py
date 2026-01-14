from django.urls import path

from .views import *

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),
    path(
        "demo_convert_account", view=demo_convert_account, name="demo_convert_account"
    ),
]
