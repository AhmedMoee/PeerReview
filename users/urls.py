from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout', views.logout_view, name= 'logout'),
    path('settings/', views.settings, name='settings'),
    path('dashboard/', views.common_dashboard, name='common_dashboard'),
    path('create_project/', views.create_project, name='create_project'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/request_to_join/<int:project_id>/', views.request_to_join, name='request_to_join'),
    path('projects/<int:project_id>/manage_requests/', views.manage_join_requests, name='manage_join_requests'),
    path('approve_request/<int:request_id>/', views.approve_join_request, name='approve_join_request'),
    path('deny_request/<int:request_id>/', views.deny_join_request, name='deny_join_request'),
    path('projects/<str:project_name>/<int:id>/', views.view_project, name='project_view'),
    path('projects/<str:project_name>/<int:id>/uploads/', views.project_uploads, name='project_uploads'),
    path('projects/<str:project_name>/<int:id>/delete/', views.delete_project, name='delete_project'),
    path('projects/<str:project_name>/<int:id>/delete-file/<int:file_id>/', views.delete_file, name='delete_file'),
    path('create-message/<int:project_id>/<int:user_id>/', views.create_message, name='create_message'),
    path('load-messages/<int:project_id>/', views.load_messages, name='load_messages'),    
    path('projects/<str:project_name>/<int:id>/view/<int:file_id>/', views.view_file, name='view_file'),
    path('project/<str:project_name>/<int:project_id>/leave/', views.leave_project, name='leave_project'),
]