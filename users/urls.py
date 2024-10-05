from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout', views.logout_view, name= 'logout'),
    path('dashboard/', views.common_dashboard, name='common_dashboard'),
]