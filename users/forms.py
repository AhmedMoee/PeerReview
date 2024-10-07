from django import forms
from .models import Upload  

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = Upload
        fields = ['name', 'file']
