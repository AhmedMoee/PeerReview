from django.db import models
from django.utils.timezone import now

class Upload(models.Model):
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.file.name
