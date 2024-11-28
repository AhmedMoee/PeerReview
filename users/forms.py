from django import forms
from .models import Upload
from .models import Project, Prompt, PromptResponse, UserProfile
from django.contrib.auth.models import User


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = Upload
        fields = ['name', 'file', 'description', 'keywords']
    
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)  # Pass project from view to the form
        super(FileUploadForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        
        # Ensure 'project' is provided
        if not self.project:
            raise forms.ValidationError("Project is required to validate uniqueness.")

        # Check if a file with the same name exists in the project
        if Upload.objects.filter(name=name, project=self.project).exists():
            raise forms.ValidationError("An upload with this name already exists in the project.")
        
        return name

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'rubric', 'review_guidelines', 'description', 'due_date', 'category', 'number_of_reviewers', 'is_private']
        labels = {
            'number_of_reviewers': 'Number of Reviewers',
            'is_private': 'Private Project',
        }
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'number_of_reviewers': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }



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

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['bio', 'specializations', 'linkedin', 'github', 'twitter']

class UploadMetaDataForm(forms.ModelForm):
    class Meta:
        model = Upload
        fields = ['name', 'description', 'keywords']
        
import re
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your last name'}),
        }
        help_texts = {
            'username': None,  # Remove the default help text for the username field
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')

        # Ensure the username is unique, excluding the current user's username
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f'Username "{username}" is not available.')

        # Restrict characters to letters and numbers only
        if not re.match(r'^[a-zA-Z0-9]+$', username):
            raise forms.ValidationError("Username can only contain letters and numbers.")

        return username