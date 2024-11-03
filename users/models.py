from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User

class Project(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    members = models.ManyToManyField(User, related_name='projects', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rubric = models.FileField(upload_to='rubrics/', blank=True, null=True)
    review_guidelines = models.FileField(upload_to='review_guidelines/', blank=True, null=True)

    def __str__(self):
        return self.name

class Upload(models.Model):
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(default=now)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='uploads')
    description = models.TextField(blank=True, null=True)  # For requirements change
    keywords = models.CharField(max_length=200, blank=True, null=True)  # For requirements change

    def __str__(self):
        return self.file.name

class JoinRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('denied', 'Denied'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.status})"

class Message(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content=models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
class Prompt(models.Model):
    upload = models.ForeignKey(Upload, on_delete=models.CASCADE, related_name='prompts')
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class PromptResponse(models.Model):
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name='responses')
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)