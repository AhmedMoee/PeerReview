from django import forms
from .models import Upload
from .models import Project

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = Upload
        fields = ['name', 'file']

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name']