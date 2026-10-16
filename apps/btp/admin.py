from django.contrib import admin



from .models import Material, ProjectSupply


# L'admin sert ici a UNE chose que les ecrans ERP ne font pas bien : saisir
# ou corriger un catalogue par lots, et verifier d'un coup d'oeil les prix
# manquants. Les ecrans metier (btp:material_list, onglet Fournitures)
# restent le chemin normal -- eux seuls bornent les listes a l'entreprise
# courante, alors que l'admin voit toutes les societes.


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['name', 'reference', 'company', 'kind', 'category',
                    'unit', 'purchase_price', 'sale_price', 'is_active']
    list_filter = ['company', 'kind', 'category', 'is_active']
    list_editable = ['purchase_price', 'sale_price', 'is_active']
    search_fields = ['name', 'reference', 'category', 'supplier_reference']
    list_select_related = ['company', 'supplier']
    autocomplete_fields = []
    ordering = ['company', 'category', 'name']


@admin.register(ProjectSupply)
class ProjectSupplyAdmin(admin.ModelAdmin):
    list_display = ['purchase_date', 'description', 'project', 'supplier',
                    'quantity', 'unit', 'unit_price', 'total_ht',
                    'invoice_reference']
    list_filter = ['project__company', 'purchase_date', 'supplier']
    search_fields = ['description', 'reference', 'invoice_reference',
                     'project__name', 'project__code']
    list_select_related = ['project', 'supplier', 'material']
    date_hierarchy = 'purchase_date'
    # total_ht est recalcule par save() : le rendre modifiable laisserait
    # croire qu'on peut le forcer, alors que la valeur serait ecrasee.
    readonly_fields = ['total_ht']
