"""
Transactional emails for web orders.
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_order_confirmation(order):
    brand_key = getattr(order, 'brand_key', 'siecle')
    brand_label = 'LUNEA' if brand_key == 'lunea' else 'SIÈCLE'

    customer_email = getattr(order, 'customer_email', None)
    if not customer_email and order.customer:
        customer_email = getattr(order.customer, 'email', None)

    if not customer_email:
        return

    template = f'emails/{brand_key}/order_confirmation.html'
    subject = f'{brand_label} — Confirmation de commande {order.order_number}'

    try:
        html_body = render_to_string(template, {
            'order': order,
            'brand_name': brand_label,
        })
    except Exception:
        html_body = None

    text_body = (
        f'Merci pour votre commande {order.order_number}.\n'
        f'Total : {order.total_ttc} €\n'
        f'Statut : Paiement confirmé\n'
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=None,
        to=[customer_email],
    )
    if html_body:
        msg.attach_alternative(html_body, 'text/html')

    try:
        msg.send()
    except Exception:
        pass
