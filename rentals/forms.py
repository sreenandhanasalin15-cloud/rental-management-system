from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import RentalItem, Booking


# -------------------------
# User Registration Form
# -------------------------
class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


# -------------------------
# Login Form
# -------------------------
class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'autofocus': True})
    )
    password = forms.CharField(widget=forms.PasswordInput)


# -------------------------
# Rental Item Form
# -------------------------
class RentalItemForm(forms.ModelForm):
    class Meta:
        model = RentalItem
        fields = ['name', 'description', 'category', 'price_per_day', 
                 'image', 'latitude', 'longitude', 'location_name',  # Added location_name here
                 'is_available', 'quantity', 'specifications']
        widgets = {
            'location_name': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly',
                'placeholder': 'Location will auto-fill from map'
            }),
            'specifications': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'placeholder': '{"Platform Height": "15-30 Ft.", "Platform Capacity": "200-250 Kgs.", ...}'
            }),
            'latitude': forms.HiddenInput(),  # Optional: hide these if you want
            'longitude': forms.HiddenInput(), # Optional: hide these if you want
        }
# -------------------------
# Booking Form
# -------------------------
class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['item', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
