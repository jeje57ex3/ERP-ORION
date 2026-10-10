"""
apps/configurator/services/crm_sync.py — Création/mise à jour CRM depuis une
soumission configurateur, AVEC déduplication par email (contrairement aux
implémentations existantes — apps.btp.guided_quote_views,
apps.websites.electricite_wizard_views — qui recréent systématiquement un
Customer/Prospect à chaque soumission).
"""
from apps.crm.models import Customer, Opportunity, Prospect

SOURCE = 'website_neostructura'


def sync_crm_lead(company, quote_request):
    """Réutilise le client/prospect existant (par email) plutôt que d'en
    recréer un à chaque demande. Ne lève jamais — une erreur CRM ne doit
    jamais faire échouer la soumission publique."""
    email = (quote_request.client_email or '').strip().lower()
    try:
        customer = None
        if email:
            customer = Customer.objects.filter(company=company, email__iexact=email).first()
        if customer is None:
            customer = Customer.objects.create(
                company=company, customer_type='individual',
                name=quote_request.client_full_name or quote_request.client_email,
                contact_name=quote_request.client_full_name,
                email=quote_request.client_email, phone=quote_request.client_phone,
                address=quote_request.address, city=quote_request.city, zip_code=quote_request.zip_code,
                notes=f'Créé automatiquement depuis le configurateur — {quote_request.reference}',
            )
        quote_request.crm_customer_id = customer.pk

        prospect = None
        if email:
            prospect = Prospect.objects.filter(company=company, email__iexact=email, is_active=True).first()
        if prospect is None:
            prospect = Prospect.objects.create(
                company=company, name=quote_request.client_full_name,
                contact_name=quote_request.client_full_name,
                email=quote_request.client_email, phone=quote_request.client_phone,
                city=quote_request.city, status='qualified', source=SOURCE,
                notes=f'Demande {quote_request.get_request_type_display()} — {quote_request.client_notes}',
            )
        else:
            # Prospect déjà connu : on garde son statut d'avancement commercial
            # (ne pas régresser un prospect "négociation" en "qualifié"),
            # on ajoute juste une trace de cette nouvelle demande.
            prospect.notes = (prospect.notes + '\n' if prospect.notes else '') + \
                f'Nouvelle demande {quote_request.reference} — {quote_request.get_request_type_display()}'
            prospect.save(update_fields=['notes'])
        quote_request.crm_prospect = prospect

        Opportunity.objects.create(
            company=company, name=f'{quote_request.get_request_type_display()} — {quote_request.reference}',
            customer=customer, prospect=prospect, stage='prospecting', probability=20,
            notes=quote_request.client_notes,
        )
        quote_request.save(update_fields=['crm_customer_id', 'crm_prospect'])
    except Exception:
        pass
