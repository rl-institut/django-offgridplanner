from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _

from offgridplanner.projects.helpers import FORM_FIELD_METADATA
from offgridplanner.projects.widgets import BatteryDesignWidget
from offgridplanner.steps.models import CustomDemand
from offgridplanner.steps.models import EnergySystemDesign
from offgridplanner.steps.models import GridDesign


def set_field_metadata(field, meta):
    label = (
        _(field.label.title()) if meta.get("verbose") == "" else meta.get("verbose")
    )  # Set verbose name
    question_icon = f'<span class="icon icon-question" data-bs-toggle="tooltip" title="{_(meta.get("help_text"))}"></span>'
    field.label = label + question_icon if meta.get("help_text") != "" else label
    field.help_text = _(meta.get("help_text", ""))  # Set help text
    # TODO change hard coded unit to customizable in the future
    field.widget.attrs["unit"] = meta.get("unit", "").replace(
        "currency", "USD"
    )  # Store unit as an attribute


class CustomModelForm(ModelForm):
    """Automatically assign labels, help_text and units to the fields"""

    def __init__(self, *args, **kwargs):
        set_db_column_attr = kwargs.pop("set_db_column_attribute", False)
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Set metadata for the field (help text, units)
            if field_name in FORM_FIELD_METADATA:
                meta = FORM_FIELD_METADATA[field_name]
                set_field_metadata(field, meta)
                # Set the db column as an attribute for the fields (relevant for group_form_by_component)
                if set_db_column_attr is True:
                    model_field = self._meta.model._meta.get_field(field_name)  # noqa: SLF001
                    field.db_column = model_field.db_column

            # Set the custom widget for the optimized/fixed capacity field
            if "settings_design" in field_name:
                field.widget = BatteryDesignWidget(
                    attrs={
                        "value": str(self.initial[field_name]).lower(),
                        "component": field.db_column.split("__")[0],
                    }
                )


class CustomDemandForm(CustomModelForm):
    percentage_fields = ["very_low", "low", "middle", "high", "very_high"]

    class Meta:
        model = CustomDemand
        exclude = ["project", "uploaded_data"]

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", {})
        instance = kwargs.get("instance")

        if instance is not None:
            for field in self.percentage_fields:
                # Serve number to user in 0-100 format
                initial[field] = self.change_percentage_format(
                    getattr(instance, field),
                    upper_limit=100,
                )

            kwargs["initial"] = initial

        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        percentage_values = {
            field: cleaned_data[field] for field in self.percentage_fields
        }
        total = round(sum(percentage_values.values(), 0))
        if total != 100:  # noqa: PLR2004
            error_message = "The sum of all shares must equal 100%."
            raise ValidationError(error_message)

        for field, value in self.cleaned_data.items():
            if field in self.percentage_fields:
                # Save number to database in 0-1 format
                self.cleaned_data[field] = self.change_percentage_format(
                    value,
                    upper_limit=1,
                )

        return cleaned_data

    @staticmethod
    def change_percentage_format(value, upper_limit=1):
        # Changes the value from a percentage range 0-1 to 0-100 and viceversa
        upper_limit_one = 1
        upper_limit_hundred = 100
        if upper_limit == upper_limit_one:
            value /= 100.0
        elif upper_limit == upper_limit_hundred:
            value *= 100
        else:
            msg = "Upper limit must be either 1 or 100"
            raise ValueError(msg)

        return value


class GridDesignForm(CustomModelForm):
    class Meta:
        model = GridDesign
        exclude = ["project"]


class EnergySystemDesignForm(CustomModelForm):
    class Meta:
        model = EnergySystemDesign
        exclude = ["project"]
