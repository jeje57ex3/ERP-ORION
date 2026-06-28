from apps.dashboard_widgets.registry import get_all_widgets, DASHBOARD_WIDGETS

import apps.dashboard_widgets.widgets  # noqa — registers all widgets on import


def user_can_see_widget(user, widget):
    permission = widget.get("permission")
    if not permission:
        return True
    if user.is_superuser:
        return True
    if getattr(user, "role", None) == "super_admin":
        return True
    if hasattr(user, "has_perm") and user.has_perm(permission):
        return True
    return False


def get_dashboard_widgets_for_user(*, user, company=None, brand_key=""):
    widgets = []

    for code, widget in get_all_widgets().items():
        if not user_can_see_widget(user, widget):
            continue

        widget_brand_key = widget.get("brand_key", "")
        if brand_key and widget_brand_key and widget_brand_key != brand_key:
            continue

        handler = widget["handler"]
        try:
            data = handler(user=user, company=company, brand_key=brand_key)
            widgets.append({
                "code": code,
                "title": widget["title"],
                "description": widget["description"],
                "module": widget["module"],
                "icon": widget["icon"],
                "order": widget["order"],
                "brand_key": widget_brand_key,
                "data": data,
            })
        except Exception as exc:
            widgets.append({
                "code": code,
                "title": widget["title"],
                "description": widget["description"],
                "module": widget["module"],
                "icon": widget["icon"],
                "order": widget["order"],
                "brand_key": widget_brand_key,
                "data": {"error": str(exc)},
            })

    return sorted(widgets, key=lambda item: item["order"])


def deduplicate_widgets():
    """
    Return a deduplicated list of widget metadata (no handlers).
    Widgets with the same title are collapsed, keeping the first registered.
    Useful for admin reporting / auditing.
    """
    seen_titles = {}
    deduped = []

    for code, widget in DASHBOARD_WIDGETS.items():
        title = widget["title"]
        if title in seen_titles:
            continue
        seen_titles[title] = code
        deduped.append({
            "code": code,
            "title": title,
            "module": widget.get("module", ""),
            "brand_key": widget.get("brand_key", ""),
            "order": widget.get("order", 100),
        })

    return sorted(deduped, key=lambda w: w["order"])


def get_widgets_by_module():
    """Group registered widgets by their module name."""
    groups: dict[str, list] = {}
    for code, widget in DASHBOARD_WIDGETS.items():
        module = widget.get("module") or "uncategorized"
        groups.setdefault(module, []).append(code)
    return groups
