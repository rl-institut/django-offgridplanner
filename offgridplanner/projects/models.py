import datetime
import uuid

import pycountry
from django.conf import settings
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.forms.models import model_to_dict
from django.utils.translation import gettext_lazy as _

from offgridplanner.users.models import User

# Create a list containing (two-letter-code, country-name) tuples from the pycountry data
COUNTRIES = [(country.alpha_2, country.name) for country in pycountry.countries]


def default_start_date():
    current_year = datetime.datetime.now(tz=datetime.UTC).year
    return datetime.datetime(current_year - 1, 1, 1, tzinfo=datetime.UTC)


class Options(models.Model):
    email_notification = models.BooleanField(default=False)
    do_demand_estimation = models.BooleanField(default=True)
    do_grid_optimization = models.BooleanField(default=True)
    do_es_design_optimization = models.BooleanField(default=True)

    def __str__(self):
        return f"Options {self.id}: Project {self.project.name}"


class Project(models.Model):
    STATUS_CHOICES = [
        ("monitoring", _("Monitoring")),
        ("analyzing", _("Analyzing")),
    ]

    name = models.CharField(max_length=51, blank=True, default="")
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    description = models.CharField(max_length=201, blank=True, default="")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    interest_rate = models.FloatField(validators=[MinValueValidator(0.0)], blank=False)
    lifetime = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(35)],
    )
    start_date = models.DateTimeField(default=default_start_date)
    temporal_resolution = models.PositiveSmallIntegerField(default=1)
    n_days = models.PositiveSmallIntegerField(default=365)
    country = models.CharField(max_length=51, choices=COUNTRIES, default="MZ")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
    )
    options = models.ForeignKey(
        Options,
        on_delete=models.SET_NULL,
        null=True,
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="analyzing"
    )

    def __str__(self):
        return f"Project {self.id}: {self.name}"

    def export(self):
        """
        Parameters
        ----------
        ...
        Returns
        -------
        A dict with the parameters describing a scenario model
        """
        dm = model_to_dict(self, exclude=["id", "user", "options"])
        if self.options:
            dm["options_data"] = model_to_dict(self.options, exclude=["id"])
        # add nodes
        # add customdemand
        return dm


class SiteExploration(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    exploration_id = models.TextField(blank=True, default="")
    consumer_count_min = models.PositiveSmallIntegerField(
        default=100, validators=[MinValueValidator(31), MaxValueValidator(500)]
    )
    diameter_max = models.FloatField(
        default=500, validators=[MinValueValidator(0.1), MaxValueValidator(10000)]
    )
    distance_from_grid_min = models.FloatField(
        default=60000, validators=[MinValueValidator(20000), MaxValueValidator(120000)]
    )
    match_distance_max = models.FloatField(
        default=5000, validators=[MinValueValidator(100), MaxValueValidator(20000)]
    )
    latest_exploration_results = models.JSONField(null=True)

    def __str__(self):
        return f"{self.exploration_id}"
