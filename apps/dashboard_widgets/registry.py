DASHBOARD_WIDGETS = {}


def register_dashboard_widget(
    code,
    title,
    description="",
    module="",
    icon="",
    order=100,
    permission=None,
    brand_key="",
):
    def decorator(func):
        if code in DASHBOARD_WIDGETS:
            existing = DASHBOARD_WIDGETS[code]
            raise ValueError(
                f"Widget code {code!r} already registered by "
                f"{existing['handler'].__module__}.{existing['handler'].__qualname__}. "
                f"Each widget code must be unique."
            )
        DASHBOARD_WIDGETS[code] = {
            "code": code,
            "title": title,
            "description": description,
            "module": module,
            "icon": icon,
            "order": order,
            "permission": permission,
            "brand_key": brand_key,
            "handler": func,
        }
        return func

    return decorator


def get_all_widgets():
    return DASHBOARD_WIDGETS


def get_widget(code):
    return DASHBOARD_WIDGETS.get(code)


def unregister_widget(code):
    """Remove a widget by code (useful in tests)."""
    DASHBOARD_WIDGETS.pop(code, None)


def list_widget_codes():
    return list(DASHBOARD_WIDGETS.keys())
