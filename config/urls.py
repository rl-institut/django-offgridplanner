# ruff: noqa
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = (
    i18n_patterns(
        path(
            "about/",
            TemplateView.as_view(template_name="pages/about.html"),
            name="about",
        ),
        path(
            "training_tasks/",
            TemplateView.as_view(template_name="pages/training_tasks.html"),
            name="training_tasks",
        ),
        path(
            "model_description/",
            TemplateView.as_view(template_name="pages/model_description.html"),
            name="model_description",
        ),
        path(
            "imprint/",
            TemplateView.as_view(template_name="pages/imprint.html"),
            name="imprint",
        ),
        path(
            "privacy/",
            TemplateView.as_view(template_name="pages/privacy.html"),
            name="privacy",
        ),
        # Django Admin, use {% url 'admin:index' %}
        path(settings.ADMIN_URL, admin.site.urls),
        # User management
        path("users/", include("offgridplanner.users.urls", namespace="users")),
        path("", include("offgridplanner.projects.urls", namespace="projects")),
        path("steps/", include("offgridplanner.steps.urls", namespace="steps")),
        path(
            "opt/",
            include("offgridplanner.optimization.urls", namespace="optimization"),
        ),
        path("accounts/", include("allauth.urls")),
    )
    + [path("i18n/", include("django.conf.urls.i18n"))]
    + [path("captcha/", include("captcha.urls"))]
    + staticfiles_urlpatterns()
)
if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()

# API URLS
urlpatterns += [
    # API base url
    path("api/", include("config.api_router")),
    # DRF auth token
    path("api/auth-token/", obtain_auth_token),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
