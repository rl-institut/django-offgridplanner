"""
This module in a FastAPI application uses Celery to handle asynchronous tasks:

1. `task_grid_opt`: Optimizes grid layouts for users and projects, with retry capabilities.
2. `task_supply_opt`: Optimizes energy supply systems for specific users and projects.
3. `task_remove_anonymous_users`: Deletes anonymous user accounts asynchronously.

Additionally, it includes functions to check the status of these tasks, identifying if they have completed, failed,
or been revoked. This setup enables efficient, asynchronous processing of complex tasks and user management.
"""

from celery.result import AsyncResult

# TODO the celery queue could still be used to send the simulation request and fetch its status
# @shared_task(
#     name="task_grid_opt",
#     force=True,
#     track_started=True,
#     autoretry_for=(Exception,),
#     retry_kwargs={"max_retries": 1, "countdown": 10},
# )
# def task_grid_opt(proj_id):
#     result = optimize_grid(proj_id)
#     return result


# @shared_task(
#     name="task_supply_opt",
#     force=True,
#     track_started=True,
#     autoretry_for=(Exception,),
#     retry_kwargs={"max_retries": 1, "countdown": 10},
# )
# def task_supply_opt(energy_system_json):
#     result = optimize_energy_system(energy_system_json)
#     return result


def get_status(task_id):
    task = AsyncResult(task_id)
    status = task.state.lower()
    return status


def revoke_task(task_id):
    task = AsyncResult(task_id)
    task.revoke(terminate=True)
    return "Task aborted"


def task_is_finished(task_id):
    status = get_status(task_id)
    return status in ["success", "failure", "revoked"]
