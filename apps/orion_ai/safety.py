import re


SENSITIVE_PATTERNS = [
    r'sk_live_[A-Za-z0-9_]+',
    r'sk_test_[A-Za-z0-9_]+',
    r'whsec_[A-Za-z0-9_]+',
    r'pk_live_[A-Za-z0-9_]+',
    r'AKIA[0-9A-Z]{16}',
    r'-----BEGIN PRIVATE KEY-----',
    r'password\s*=\s*\S+',
    r'SECRET_KEY\s*=\s*\S+',
]

DANGEROUS_ACTIONS = {
    'delete_order',
    'refund_payment',
    'delete_customer',
    'disable_shop',
    'run_system_update',
    'run_database_migration',
    'restart_server',
    'change_stripe_secret',
    'run_failover',
}

WRITE_ACTIONS = {
    'update_shop_settings',
    'create_discount',
    'update_product_stock',
    'create_customer_note',
    'send_email',
    'create_order_note',
    'run_repair',
    'update_shop_maintenance',
    'run_health_scan',
}

SENSITIVE_KEYS = {
    'secret', 'password', 'token', 'api_key', 'webhook',
    'private_key', 'access_key', 'auth', 'credential',
}


def redact_sensitive_text(text):
    if not text:
        return text
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = re.sub(pattern, '[SECRET_REDACTED]', redacted, flags=re.IGNORECASE)
    return redacted


def redact_payload(payload):
    if isinstance(payload, dict):
        clean = {}
        for key, value in payload.items():
            lowered = key.lower()
            if any(word in lowered for word in SENSITIVE_KEYS):
                clean[key] = '[SECRET_REDACTED]'
            else:
                clean[key] = redact_payload(value)
        return clean
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, str):
        return redact_sensitive_text(payload)
    return payload


def is_dangerous_action(action_code):
    return action_code in DANGEROUS_ACTIONS


def is_write_action(action_code):
    return action_code in WRITE_ACTIONS or action_code in DANGEROUS_ACTIONS


def validate_user_prompt(prompt):
    if not prompt:
        return False, 'Le message ne peut pas être vide.'
    if len(prompt) > 50000:
        return False, 'Message trop long.'
    return True, ''
