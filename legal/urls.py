"""
Legal pages URLs
"""
from django.urls import path
from . import views

app_name = 'legal'

urlpatterns = [
    path('privacidad/', views.privacy_view, name='privacy'),
    path('terminos/', views.terms_view, name='terms'),
    path('cookies/', views.cookies_view, name='cookies'),
]
