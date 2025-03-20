from django.forms import CheckboxInput


class BatteryDesignWidget(CheckboxInput):
    template_name = "widgets/battery_design_widget.html"
