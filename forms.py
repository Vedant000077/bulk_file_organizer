from django import forms
from .models import CustomRule


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class UploadForm(forms.Form):
    files = forms.FileField(widget=MultipleFileInput(attrs={'accept': '*'}), required=False)
    job_name = forms.CharField(
        required=False,
        initial='Untitled Job'
    )
    rename_pattern = forms.CharField(
        required=False,
        initial='{index}_{name}'
    )


class RuleForm(forms.ModelForm):
    class Meta:
        model = CustomRule
        fields = ['name', 'rule_type', 'match_value', 'target_folder', 'enabled']
