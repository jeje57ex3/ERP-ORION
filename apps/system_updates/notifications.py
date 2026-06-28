def notify_update_event(title, message, level='info'):
    try:
        from apps.smart_alerts.models import SmartAlert
        SmartAlert.objects.create(
            company=None,
            title=title,
            message=message,
            source_module='system_updates',
            priority='critical' if level == 'error' else 'normal',
        )
    except Exception:
        pass
