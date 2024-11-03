from django import forms
from .models import Upload
from .models import Project, Prompt, PromptResponse


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
        fields = ['name', 'description', 'due_date', 'category']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'})
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