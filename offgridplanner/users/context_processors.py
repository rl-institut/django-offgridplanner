from django.conf import settings


def allauth_settings(request):
    """Expose some settings from django-allauth in templates."""
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }


def app_version(request):
    """Expose version number in templates."""
    return {
        "APP_VERSION_NUMBER": settings.APP_VERSION_NUMBER,
    }
