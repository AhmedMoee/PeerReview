from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout', views.logout_view, name= 'logout'),
    path('dashboard/', views.common_dashboard, name='common_dashboard'),
    path('create_project/', views.create_project, name='create_project'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/request_to_join/<int:project_id>/', views.request_to_join, name='request_to_join'),
]