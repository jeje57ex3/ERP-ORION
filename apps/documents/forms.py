from django import forms
from .models import Document, DocumentCategory


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'title', 'document_type', 'category', 'description',
            'file', 'version', 'tags', 'is_confidential',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'tag1, tag2, tag3...'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['category'].queryset = DocumentCategory.objects.filter(company=company)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'form-control form-control-sm')
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')
