from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):

    ROLE_CHOICES = (
        ('user', 'User'),
        ('owner', 'Owner'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.username


from django.conf import settings

class OwnerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    business_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    business_address = models.TextField()

    government_id_number = models.CharField(max_length=50)
    business_license_number = models.CharField(max_length=50)

    id_proof = models.FileField(upload_to='owner_documents/id_proofs/')
    business_license_document = models.FileField(upload_to='owner_documents/licenses/')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Owner Profile"
