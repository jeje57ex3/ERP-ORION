"""apps/fiscal_pt/admin.py — L'administration Django, en lecture seule.

POURQUOI LA LECTURE SEULE ICI

L'administration Django contourne les formulaires et, pour les documents
fiscaux, contournerait la seule garantie qui compte : l'immuabilité.
`DocumentFiscal.save()` refuse déjà toute modification, mais un écran qui
PROPOSE de modifier pour échouer ensuite est un écran qui trompe. On
retire donc la proposition.

La clé privée n'est pas exposée non plus : l'administration affiche les
champs tels qu'ils sont en base, et montrer un secret chiffré n'a aucune
utilité tout en donnant une cible.
"""

from django.contrib import admin

from .models import (CleDeSignature, DocumentFiscal, ParametresFiscauxPT,
                     SerieFiscale)


@admin.register(ParametresFiscauxPT)
class ParametresAdmin(admin.ModelAdmin):
    list_display = ('company', 'est_actif', 'nif', 'numero_de_certificat',
                    'region_par_defaut')
    list_filter = ('est_actif', 'region_par_defaut')
    search_fields = ('company__name', 'nif')


@admin.register(CleDeSignature)
class CleAdmin(admin.ModelAdmin):
    list_display = ('company', 'version', 'est_active', 'cree_le')
    list_filter = ('est_active',)
    search_fields = ('company__name',)
    readonly_fields = ('version', 'pem_publique', 'cree_le')
    exclude = ('pem_privee_chiffree',)

    def has_add_permission(self, request):
        """Les clés se créent depuis l'écran de conformité.

        Une clé ajoutée ici aurait une partie privée vide — donc
        incapable de signer — et le défaut ne se verrait qu'à la première
        facture.
        """
        return False


@admin.register(SerieFiscale)
class SerieAdmin(admin.ModelAdmin):
    list_display = ('company', 'type_document', 'nom', 'region',
                    'code_de_validation', 'prochain_numero', 'est_active')
    list_filter = ('type_document', 'region', 'est_active')
    search_fields = ('company__name', 'nom', 'code_de_validation')
    readonly_fields = ('prochain_numero',)


@admin.register(DocumentFiscal)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('numero', 'company', 'date_document', 'total', 'atcud',
                    'version_cle')
    list_filter = ('serie', 'etat', 'date_document')
    search_fields = ('numero', 'atcud', 'nif_acquereur')
    date_hierarchy = 'date_document'

    def has_add_permission(self, request):
        """Un document se crée par `DocumentFiscal.emettre`, qui numérote,
        signe et chaîne dans une seule transaction. Un ajout à la main
        produirait un document sans signature valide au milieu d'une
        chaîne, et tous les suivants deviendraient invérifiables."""
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        """Supprimer un document rompt la chaîne de la série, et
        l'administration le constate au premier contrôle."""
        return False
