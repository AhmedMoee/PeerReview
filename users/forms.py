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
            'content': forms.Textarea(attrs={
                'placeholder': 'Write your prompt here...',
                'rows': 3,   # Adjust the number of rows as needed
                'cols': 50,  # Adjust the number of columns as needed
                'style': 'width: 100%; max-width: 100%;',  # Ensures it’s responsive
            }),
        }

class PromptResponseForm(forms.ModelForm):
    class Meta:
        model = PromptResponse
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'placeholder': 'Write your response...',
                'rows': 5,   # Adjust the number of rows as needed
                'cols': 80,  # Adjust the number of columns as needed
                'style': 'width: 100%; max-width: 100%;',  # Ensures it’s responsive
            }),
        }