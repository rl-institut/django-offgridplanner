from django.forms import ModelForm
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _

from offgridplanner.steps.forms import CustomModelForm

from .models import *


class ProjectForm(CustomModelForm):
    class Meta:
        model = Project
        exclude = [
            "date_created",
            "date_updated",
            "start_date",
            "temporal_resolution",
            "user",
            "options",
        ]
        widgets = {"description": Textarea(attrs={"rows": 7})}


OPTIONS_LABELS = {
    "do_demand_estimation": _(
        "Demand estimation",
    ),  # TODO when set False then display warning If you keep the demand estimation option enabled, you can choose later between estimating demand or using a custom demand time series. If the demand estimation function is not used, a corresponding time series must be uploaded later in the 'Demand Estimation' section.
    "do_grid_optimization": _(
        "Spatial Grid Optimization",
    ),  # TODO if set False then disable step 'grid_design' and display warning A demand is required for the design optimization of energy converters. Demand estimation requires information about consumers, which is defined in the 'Consumer Selection' section using the integrated mapping system. Therefore, even if grid planning is not carried out, consumers must still be specified unless a custom demand time series is uploaded in the 'Demand Estimation' section. In that case, also deactivate 'Demand Estimation' to skip the consumer definition step.
    "do_es_design_optimization": _(
        "Energy Converter Design Optimization",
    ),  # TODO if set False then disable step 'energy_system_design'
}


class OptionForm(ModelForm):
    class Meta:
        model = Options
        fields = list(OPTIONS_LABELS)
        labels = OPTIONS_LABELS


class BoundForm(ModelForm):
    class Meta:
        model = Options
        fields = ["latitude_min", "latitude_max", "longitude_min", "longitude_max"]
        labels = {
            "latitude_min": _("Latitude min"),
            "latitude_max": _("Latitude max"),
            "longitude_min": _("Longitude min"),
            "longitude_max": _("Longitude max"),
        }
