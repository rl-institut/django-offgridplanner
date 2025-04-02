from celery import shared_task

from .models import User


@shared_task()
def get_users_count():
    """A pointless Celery task to demonstrate usage."""
    return User.objects.count()


@shared_task(name="task_remove_anonymous_users", force=True, track_started=True)
def task_remove_anonymous_users(user_id):
    # TODO migrated from tier_spatial_planning, check if still useful
    try:
        user = User.objects.get(id=user_id)
        user.delete()
    except User.DoesNotExist:
        return f"User {user_id} does not exist"
    return f"User {user_id} was deleted"
