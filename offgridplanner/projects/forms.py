from django import forms
from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from .models import *


class TooltipModelForm(ModelForm):
    """Class to automatize the assignation and translation of the labels, help_text and units"""

    def __init__(self, *args, **kwargs):
        super(TooltipModelForm, self).__init__(*args, **kwargs)
        for fieldname, field in self.fields.items():
            set_parameter_info(fieldname, field)


PROJECT_LABELS = {
            "name": _("Project Name"),
            "description": _("Project Description"),
            "interest_rate" :_("Interest Rate"),
            "lifetime" : _("Project Lifetime"),
            "n_days": _("Simulation Period"),
            "do_demand_estimation" : _("Demand estimation"), # TODO when set False then display warning If you keep the demand estimation option enabled, you can choose later between estimating demand or using a custom demand time series. If the demand estimation function is not used, a corresponding time series must be uploaded later in the 'Demand Estimation' section.
            "do_grid_optimization" : _("Spatial Grid Optimization"), # TODO if set False then disable step 'grid_design' and display warning A demand is required for the design optimization of energy converters. Demand estimation requires information about consumers, which is defined in the 'Consumer Selection' section using the integrated mapping system. Therefore, even if grid planning is not carried out, consumers must still be specified unless a custom demand time series is uploaded in the 'Demand Estimation' section. In that case, also deactivate 'Demand Estimation' to skip the consumer definition step.
            "do_es_design_optimization" : _("Energy Converter Design Optimization"), # TODO if set False then disable step 'energy_system_design'
        }
PROJECT_HELPTEXTS = {
            "name": _("Offgridplanner was developed to guide users through the entire planning process of an off-grid system, from demand estimation and spatial grid optimization to design optimization and unit commitment of energy converters. However, individual planning steps can be skipped if needed; simply deselect the relevant options accordingly."),
            "interest_rate" :_("The interest rate in investment calculations signifies the cost of capital and the potential return from an alternative investment of similar risk. It helps express the time value of money, crucial for determining the present value of future cash flows. This assists in evaluating and comparing investment opportunities. Default value of 12.3% is taken from World Bank reported average lending interest rate data of 2022. Please make sure to check this value for your project."),
            "lifetime" : _("The period during which the off grid will be in operation. Components whose lifetime is below that of the project lifetime must be replaced during operation, and this replacement must be taken into account in the cost calculation. In addition, the residual value of the components is determined at the end of the project lifetime."),
            "n_days": _("Number of days in the modeling period for the unit commitment of the energy converters. Nonetheless, for economic calculations, the project lifetime is used."),
        }
PROJECT_TOOLTIP_LABELS = {}
for k,label in PROJECT_LABELS.items():
    if k in PROJECT_HELPTEXTS:
        label = label + mark_safe(f' <span class="icon icon-question" data-bs-toggle="tooltip" title="{PROJECT_HELPTEXTS[k]}"></span>')
    PROJECT_TOOLTIP_LABELS[k] = label
class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = [k for k in PROJECT_LABELS.keys()]
        labels = PROJECT_LABELS
        # help_texts = PROJECT_HELPTEXTS



    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['placeholder'] = _("Simulation and optimization of power supply and grid layout for an off-grid system in a rural settlement.")

        # for field in self.fields:
        #     if self.fields[field].help_text is not None:
        #         help_text = (
        #             self.fields[field].help_text
        #             + ". "
        #             + _("Click on the icon for more help")
        #             + "."
        #         )
        #         self.fields[field].help_text = None
        #     else:
        #         help_text = ""
        #     if self.fields[field].label is not None:
        #         question_icon = f'<span class="icon icon-question" data-bs-toggle="tooltip" title="{help_text}"></span>'
        #
        #         self.fields[field].label = self.fields[field].label + question_icon
