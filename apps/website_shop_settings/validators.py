from django.core.exceptions import ValidationError


def validate_brand_key(value):
    allowed = {'siecle', 'lunea'}
    if value not in allowed:
        raise ValidationError(f"brand_key doit être l'un de : {', '.join(sorted(allowed))}")


def validate_stripe_publishable_key(value):
    if value and not (value.startswith('pk_test_') or value.startswith('pk_live_')):
        raise ValidationError(
            "La clé publique Stripe doit commencer par 'pk_test_' ou 'pk_live_'."
        )


def validate_stripe_secret_key(value):
    if value and not (value.startswith('sk_test_') or value.startswith('sk_live_')):
        raise ValidationError(
            "La clé secrète Stripe doit commencer par 'sk_test_' ou 'sk_live_'."
        )
