from django.urls import path
from . import views

urlpatterns = [
    path('connect/', views.github_connect, name='github_connect'),
    path('connect/github_redirect/', views.github_redirect, name='github_redirect'),
    path('oauth/callback/', views.github_callback, name='github_callback'),
    path('webhook/', views.github_webhook, name='github_webhook'),  # Add the webhook URL here
]
