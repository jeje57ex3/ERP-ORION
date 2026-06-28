from django import forms
from .models import (
    ContactMessage, QuoteRequest, Website, WebsitePage, BlogPost,
    StoreCategory, StoreProduct, StoreOrder,
)


def _css(form):
    for field in form.fields.values():
        w = field.widget
        if isinstance(w, forms.CheckboxInput):
            w.attrs.setdefault('class', 'form-check-input')
        elif isinstance(w, (forms.Select, forms.SelectMultiple)):
            w.attrs.setdefault('class', 'form-select form-select-sm')
        elif isinstance(w, forms.Textarea):
            w.attrs.setdefault('class', 'form-control form-control-sm')
            w.attrs.setdefault('rows', 3)
        else:
            w.attrs.setdefault('class', 'form-control form-control-sm')


# ─── FORMULAIRES PUBLICS ──────────────────────────────────────────────────────

class ContactForm(forms.ModelForm):
    website_url_field = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre nom'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre@email.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+33 6 00 00 00 00'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Objet de votre message'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Votre message...'}),
        }
        labels = {
            'name': 'Nom complet', 'phone': 'Téléphone (optionnel)', 'subject': 'Sujet (optionnel)',
        }


class QuoteRequestForm(forms.ModelForm):
    website_url_field = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = QuoteRequest
        fields = ['company_name', 'name', 'email', 'phone', 'project_type', 'description', 'budget', 'deadline', 'attachments']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de votre société'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre nom'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre@email.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+33 6 00 00 00 00'}),
            'project_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Type de projet'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Décrivez votre projet...'}),
            'budget': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: 5 000 - 10 000 €'}),
            'deadline': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: dans 3 mois'}),
        }


# ─── FORMULAIRES ADMIN — SITES WEB ────────────────────────────────────────────

class WebsiteAdminForm(forms.ModelForm):
    class Meta:
        model = Website
        fields = [
            'name', 'site_type', 'status', 'domain', 'subdomain', 'language',
            'currency', 'country', 'contact_email', 'contact_phone', 'address',
            'meta_title', 'meta_description', 'google_analytics_id',
            'facebook_url', 'instagram_url', 'twitter_url', 'linkedin_url',
            'youtube_url', 'tiktok_url', 'is_active',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _css(self)


class WebsiteShowcaseCreateForm(forms.ModelForm):
    """Wizard de création d'un site vitrine avec pages automatiques."""
    class Meta:
        model = Website
        fields = [
            'name', 'domain', 'subdomain', 'language',
            'contact_email', 'contact_phone', 'address',
            'facebook_url', 'instagram_url', 'linkedin_url',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _css(self)


class WebsiteStoreCreateForm(forms.ModelForm):
    """Wizard de création d'une boutique en ligne avec pages automatiques."""
    terms_and_conditions = forms.CharField(
        label='Conditions générales de vente', required=False,
        widget=forms.Textarea(attrs={'rows': 4}),
    )
    return_policy = forms.CharField(
        label='Politique de retour', required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    shipping_policy = forms.CharField(
        label='Politique de livraison', required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    class Meta:
        model = Website
        fields = [
            'name', 'domain', 'subdomain', 'language', 'currency', 'country',
            'contact_email', 'contact_phone',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _css(self)


class WebsitePageAdminForm(forms.ModelForm):
    class Meta:
        model = WebsitePage
        fields = [
            'website', 'page_type', 'title', 'slug', 'content', 'status',
            'order', 'is_homepage', 'show_in_menu', 'meta_title', 'meta_description',
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['website'].queryset = Website.objects.filter(company=company)
        _css(self)


class BlogPostAdminForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = [
            'website', 'category', 'title', 'slug', 'excerpt', 'content',
            'tags', 'status', 'reading_time', 'meta_title', 'meta_description',
        ]
        widgets = {
            'excerpt': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 12}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from .models import BlogCategory
            self.fields['website'].queryset = Website.objects.filter(company=company)
            self.fields['category'].queryset = BlogCategory.objects.filter(website__company=company)
            self.fields['category'].required = False
        _css(self)


# ─── FORMULAIRES BOUTIQUE ─────────────────────────────────────────────────────

class StoreCategoryForm(forms.ModelForm):
    class Meta:
        model = StoreCategory
        fields = ['name', 'parent', 'description', 'order', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, website=None, **kwargs):
        super().__init__(*args, **kwargs)
        if website:
            self.fields['parent'].queryset = StoreCategory.objects.filter(website=website)
        self.fields['parent'].required = False
        _css(self)


class StoreProductForm(forms.ModelForm):
    class Meta:
        model = StoreProduct
        fields = [
            'name', 'category', 'erp_product', 'short_description', 'description',
            'price', 'compare_at_price', 'sku', 'stock_quantity', 'stock_from_erp',
            'status', 'is_featured', 'weight_kg', 'meta_title', 'meta_description',
        ]
        widgets = {
            'short_description': forms.Textarea(attrs={'rows': 2}),
            'description': forms.Textarea(attrs={'rows': 6}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, website=None, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if website:
            self.fields['category'].queryset = StoreCategory.objects.filter(website=website)
        if company:
            from apps.inventory.models import Product
            self.fields['erp_product'].queryset = Product.objects.filter(company=company, is_active=True)
        self.fields['category'].required = False
        self.fields['erp_product'].required = False
        self.fields['compare_at_price'].required = False
        _css(self)


class StoreOrderStatusForm(forms.ModelForm):
    class Meta:
        model = StoreOrder
        fields = ['status', 'payment_status', 'shipping_method', 'carrier', 'tracking_number', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _css(self)
