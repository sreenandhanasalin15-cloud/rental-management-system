from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .forms import UserRegisterForm, OwnerRegisterForm



def index(request):
    return render(request,"accounts/index.html")

# Home → redirect to login
# def home_redirect(request):
#     return redirect('login')


#  User Register
def user_register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'user'
            user.is_verified = True   # normal users don't need approval
            user.save()
            login(request, user)
            return redirect('rentals:user_dashboard')
    else:
        form = UserRegisterForm()

    return render(request, 'accounts/user_register.html', {'form': form})

#  owner Register

from .models import OwnerProfile

def owner_register_view(request):

    if request.method == 'POST':
        form = OwnerRegisterForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'owner'
            user.is_verified = False
            user.save()

            # Create OwnerProfile
            OwnerProfile.objects.create(
                user=user,
                business_name=form.cleaned_data['business_name'],
                phone_number=form.cleaned_data['phone_number'],
                business_address=form.cleaned_data['business_address'],
                government_id_number=form.cleaned_data['government_id_number'],
                business_license_number=form.cleaned_data['business_license_number'],
                id_proof=form.cleaned_data['id_proof'],
                business_license_document=form.cleaned_data['business_license_document'],
            )

            return redirect('login')

    else:
        form = OwnerRegisterForm()

    return render(request, 'accounts/owner_register.html', {'form': form})



def verification_pending(request):
    return render(request, 'accounts/verification_pending.html')


# Login
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

def login_view(request):

    if request.user.is_authenticated:
        return redirect_based_on_role(request.user)

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            user = authenticate(username=username, password=password)

            if user is not None:

                # 🚨 If owner and not verified
                if user.role == 'owner' and not user.is_verified:
                    login(request, user)  # login but restrict access
                    return redirect('verification_pending')

                login(request, user)
                return redirect_based_on_role(user)
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


from django.contrib.auth.decorators import login_required

# @login_required
# def user_dashboard(request):
#     return render(request, 'accounts/user_dashboard.html')


@login_required
def owner_dashboard(request):
    if request.user.role != 'owner':
        return redirect('user_dashboard')

    if not request.user.is_verified:
        return redirect('verification_pending')

    return render(request, 'accounts/owner_dashboard.html')



def redirect_based_on_role(user):
    if user.role == 'owner':
        return redirect('rentals:owner_dashboard')
    else:
        return redirect('rentals:user_dashboard')

# Dashboard
# @login_required
# def dashboard_view(request):
#     return render(request, 'accounts/dashboard.html')


from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

