import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models


def default_start_date():
    current_year = datetime.datetime.now().year
    return datetime.datetime(current_year - 1, 1, 1)


class Project(models.Model):
    def __str__(self):
        return f"Project {self.id} - {self.project_id}: {self.project_name}"

    # id = models.PositiveSmallIntegerField(db_index=True)
    name = models.CharField(max_length=51, null=True, blank=True)
    description = models.CharField(max_length=201, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    interest_rate = models.FloatField(validators=[MinValueValidator(0.0)], blank=False)
    lifetime = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(35)],
    )
    start_date = models.DateTimeField(default=default_start_date)
    temporal_resolution = models.PositiveSmallIntegerField(default=1)
    n_days = models.PositiveSmallIntegerField(default=365)
    status = models.CharField(max_length=25, default="not yet started")
    email_notification = models.BooleanField(default=False)

    do_demand_estimation = models.BooleanField(default=True)
    do_grid_optimization = models.BooleanField(default=True)
    do_es_design_optimization = models.BooleanField(default=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
    )
