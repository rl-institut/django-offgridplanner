from django import template

register = template.Library()


@register.simple_tag
def setvar(val=None):
    return val


@register.filter
def getfield(value, arg):
    """Gets an attribute of an object dynamically from a string name"""
    if hasattr(value, "fields"):
        fields = value.fields
        if str(arg) in fields:
            field = str(fields[str(arg)])
            return field


@register.filter
def getkey(mapping, key):
    return mapping.get(key, "")


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_field(form, key):
    return form.fields[key].get_bound_field(form, key)


@register.filter
def has_field(form, key):
    return key in form.fields
