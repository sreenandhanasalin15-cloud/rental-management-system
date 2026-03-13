from django import forms

from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class UserRegisterForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, OwnerProfile


class OwnerRegisterForm(UserCreationForm):

    business_name = forms.CharField(max_length=150)
    phone_number = forms.CharField(max_length=15)
    business_address = forms.CharField(widget=forms.Textarea)

    government_id_number = forms.CharField(max_length=50)
    business_license_number = forms.CharField(max_length=50)

    id_proof = forms.FileField()
    business_license_document = forms.FileField()

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

