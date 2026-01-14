from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import DemoAccount

User = get_user_model()


@shared_task()
def get_users_count():
    """A pointless Celery task to demonstrate usage."""
    return User.objects.count()


@shared_task
def cleanup_expired_demo_accounts(batch_size: int = 500) -> int:
    """
    Deletes expired demo users (and cascades their demo-owned objects).
    Returns number of users deleted.
    """
    now = timezone.now()

    # Get expired demo user ids
    expired_user_ids = list(
        DemoAccount.objects.filter(expires_at__lte=now).values_list(
            "user_id", flat=True
        )[:batch_size]
    )

    if not expired_user_ids:
        return 0

    deleted_count, _ = User.objects.filter(id__in=expired_user_ids).delete()
    return deleted_count
