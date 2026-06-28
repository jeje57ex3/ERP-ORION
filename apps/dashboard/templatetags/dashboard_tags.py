from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    if isinstance(d, dict):
        return d.get(key, {})
    return {}


@register.filter
def multiply(value, arg):
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def widget_col_class(width):
    return f'col-12 col-md-{width}'
