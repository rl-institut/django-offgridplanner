from django.forms import RadioSelect


class BatteryDesignWidget(RadioSelect):
    template_name = "widgets/battery_design_widget.html"

    class Media:
        js = "js/energy-system-design.js"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update(
            {
                "onchange": f"check_optimization_strategy('{self.attrs.get("component", "")}')"
            }
        )
