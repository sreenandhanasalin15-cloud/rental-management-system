from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("", views.index, name="index"),
    path('register/user/', views.user_register_view, name='user_register'),
    path('register/owner/', views.owner_register_view, name='owner_register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verification-pending/', views.verification_pending, name='verification_pending'),
]