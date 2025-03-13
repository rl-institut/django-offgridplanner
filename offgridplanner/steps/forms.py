from django.forms import ModelForm

from offgridplanner.steps.models import CustomDemand, GridDesign


class CustomDemandForm(ModelForm):
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
        if total != 1:
            # TODO tbd how we want to handle this
            # raise ValidationError("The sum of all shares must equal 100%.")
            print("The sum of all shares does not equal 100%.")

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
        if upper_limit == 1:
            value /= 100.0
        elif upper_limit == 100:
            value *= 100
        else:
            raise ValueError("Upper limit must be either 1 or 100")

        return value


class GridDesignForm(ModelForm):
    class Meta:
        model = GridDesign
        exclude = ["project"]
