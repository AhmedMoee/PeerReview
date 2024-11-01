from django import forms
from .models import Upload
from .models import Project, Prompt, PromptResponse


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = Upload
        fields = ['name', 'file', 'description', 'keywords']

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name']
        


class PromptForm(forms.ModelForm):
    class Meta:
        model = Prompt
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'placeholder': 'Enter your prompt here...'}),
        }

class PromptResponseForm(forms.ModelForm):
    class Meta:
        model = PromptResponse
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'placeholder': 'Enter your response here...'}),
        }