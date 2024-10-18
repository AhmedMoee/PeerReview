from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import Upload, JoinRequest, Project, Message, User
from .forms import FileUploadForm
from .forms import ProjectForm
from typing import AsyncGenerator
import asyncio
import json
import random
from datetime import datetime
from django.http import HttpRequest, StreamingHttpResponse, HttpResponse, JsonResponse

from mysite.settings import AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME
import boto3

def home(request):
    # If the user is authenticated, redirect to the dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    # Otherwise, render the home page (with the Google login option)
    return render(request, 'home.html')
    

def dashboard(request):
    if request.user.groups.filter(name='PMA Administrators').exists():
        # Render the PMA Administrator dashboard
        return render(request, 'pma_admin_dashboard.html')  
    else:
        # Render the Common User dashboard
        return render(request, 'common_dashboard.html')

def logout_view(request):
    logout(request)
    return redirect('/')

def common_dashboard(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('common_dashboard')
    else:
        form = FileUploadForm()
    
    return render(request, 'common_dashboard.html', {'form': form})

def upload_list(request):
    s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
    bucket_name = AWS_STORAGE_BUCKET_NAME
    prefix = 'uploads/'
    
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        files = response.get('Contents', [])
        file_list = [{'name': file['Key'], 'url': f'https://{bucket_name}.s3.amazonaws.com/{file["Key"]}'} for file in files]
    except Exception as e:
        print(f'Error fetching files: {e}')
        file_list = []

    return render(request, 'upload_list.html', {'files': file_list})

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            s3 = boto3.client('s3')
            
            try:
                print(f'Uploading {uploaded_file.name} to S3...')
                s3.upload_fileobj(
                    uploaded_file,
                    AWS_STORAGE_BUCKET_NAME,
                    f'uploads/{uploaded_file.name}'
                )
                print('Upload successful!')
                return redirect('upload_list')
            except Exception as e:
                print(f'Error uploading file: {e}') 
    else:
        form = FileUploadForm()
    return render(request, 'project_view.html', {'form': form})

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            project.members.add(request.user)
            return redirect('project_list')
    else:
        form = ProjectForm()

    return render(request, 'create_project.html', {'form': form})


from django.shortcuts import render
from .models import Project

def project_list(request):
    projects = Project.objects.all()
    project_status = {}

    # Check if the user is a PMA Administrator
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()

    # Only process membership statuses for common users
    if request.user.is_authenticated and not is_pma_admin:
        for project in projects:
            if request.user in project.members.all():
                project_status[project.id] = 'member'
            elif JoinRequest.objects.filter(user=request.user, project=project, status='pending').exists():
                project_status[project.id] = 'pending'
            else:
                project_status[project.id] = 'not_member'

    project_permissions = {}
    for project in projects:
        is_owner = project.owner == request.user
        project_permissions[project.id] = is_owner or is_pma_admin

    return render(request, 'project_list.html', {
        'projects': projects,
        'project_status': project_status,
        'is_pma_admin': is_pma_admin, 
        'project_permissions': project_permissions
    })


def request_to_join(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    # Check if the user has already made a request for this project
    if JoinRequest.objects.filter(user=request.user, project=project).exists():
        messages.error(request, 'You have already requested to join this project.')
    else:
        # Create a new JoinRequest object
        JoinRequest.objects.create(user=request.user, project=project)
        messages.success(request, 'Your request to join the project has been submitted.')

    return redirect('project_list')

@login_required
def manage_join_requests(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    # Ensure the current user is the owner of the project
    if project.owner != request.user:
        return redirect('project_list')

    pending_requests = JoinRequest.objects.filter(project=project, status='pending')
    return render(request, 'manage_join_requests.html', {'project': project, 'pending_requests': pending_requests})

@login_required
def approve_join_request(request, request_id):
    join_request = get_object_or_404(JoinRequest, id=request_id)

    # Ensure the current user is the owner of the project
    if join_request.project.owner != request.user:
        return redirect('project_list')

    join_request.status = 'accepted'
    join_request.save()

    join_request.project.members.add(join_request.user)
    return redirect('manage_join_requests', project_id=join_request.project.id)

@login_required
def deny_join_request(request, request_id):
    join_request = get_object_or_404(JoinRequest, id=request_id)

    # Ensure the current user is the owner of the project
    if join_request.project.owner != request.user:
        return redirect('project_list')

    join_request.status = 'denied'
    join_request.save()

    return redirect('manage_join_requests', project_id=join_request.project.id)

def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if request.user == project.owner:
        pending_requests = JoinRequest.objects.filter(project=project, status='pending')
    else:
        pending_requests = None

    return render(request, 'project_detail.html', {
        'project': project,
        'pending_requests': pending_requests,
    })

def project_uploads(request, project_name, id):
    project = get_object_or_404(Project, id=id)
    s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
    bucket_name = AWS_STORAGE_BUCKET_NAME
    prefix = f'{project_name}/'

    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        files = response.get('Contents', [])
        
        file_list = []
        for file in files:
            file_key = file['Key']
            if f"{project.name.lower()}/" in file_key.lower(): 
                file_list.append({
                    'name': file_key.split('/')[-1],
                    'url': f'https://{bucket_name}.s3.amazonaws.com/{file_key}'
                })
    except Exception as e:
        print(f'Error fetching files: {e}')
        file_list = []

    is_owner_or_admin = (project.owner == request.user or request.user.groups.filter(name='PMA Administrators').exists())

    context = {
        'project': project,
        'files': file_list,
        'is_owner_or_admin': is_owner_or_admin,  
    }

    return render(request, 'project_uploads.html', context)

def view_project(request, project_name, id):
    project = get_object_or_404(Project, id=id)

    if project.name.lower() != project_name.lower():  
        return redirect('project_list')
    
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()


    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            s3 = boto3.client('s3')
            
            try:
                print(f'Uploading {uploaded_file.name} to S3...')
                s3.upload_fileobj(
                    uploaded_file,
                    AWS_STORAGE_BUCKET_NAME,
                    f'{project_name}/{uploaded_file.name}'
                )
                print('Upload successful!')
                return redirect('project_uploads', project_name=project.name, id=project.id)
            except Exception as e:
                print(f'Error uploading file: {e}') 
    else:
        form = FileUploadForm()

    return render(request, 'project_view.html', {
        'project': project,
        'form': form,
        'is_pma_admin': is_pma_admin
    })

def delete_project(request, project_name, id):
    project = get_object_or_404(Project, id=id)

    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    is_project_owner = project.owner == request.user
    
    if is_pma_admin or is_project_owner:
        # Delete the project and associated files if any
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('project_list')
    else:
        messages.error(request, f"You don't have permission to delete {project_name}.")
        return redirect('project_view', project_name=project.name, id=project.id)
    
def delete_file(request, project_name, id, file_name):
    project = get_object_or_404(Project, id=id, name=project_name)

    if project.owner == request.user or request.user.groups.filter(name='PMA Administrators').exists():
        s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
        bucket_name = AWS_STORAGE_BUCKET_NAME
        file_key = f"{project_name}/{file_name}"

        try:
            # Delete the file from S3
            s3.delete_object(Bucket=bucket_name, Key=file_key)
            messages.success(request, f"File '{file_name}' has been deleted.")
        except Exception as e:
            print(f"Error deleting file: {e}")
            messages.error(request, "An error occurred while trying to delete the file.")
    else:
        messages.error(request, "You do not have permission to delete this file.")

    return redirect('project_uploads', project_name=project_name, id=id)



def create_message(request, project_id, user_id):
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            user = get_object_or_404(User, id=user_id)
            project = get_object_or_404(Project, id=project_id)
            Message.objects.create(content=content, project=project, user=user)
            return JsonResponse({'status': 'Message sent'})
    return JsonResponse({'error': 'Invalid request'}, status=400)

def load_messages(request, project_id):
    messages = Message.objects.filter(project_id=project_id).order_by('created_at')
    messages_list = [{'content': message.content, 'username':message.user.username} for message in messages]
    return JsonResponse({'messages': messages_list})

# def create_message(request, id) -> HttpResponse:
#     content = request.POST.get("content")
#     user = get_object_or_404(User, request.POST.get("user_id"))
#     project_id = id
#     project = get_object_or_404(Project, id=project_id)

#     if content:
#         Message.objects.create(user=user, content=content, project=project)
#         return HttpResponse(status=201)
#     else:
#         return HttpResponse(status=200)

# async def stream_messages(request: HttpRequest, id) -> StreamingHttpResponse:
#     project_id = id
#     async def event_stream():
#         """
#         We use this function to send a continuous stream of data 
#         to the connected clients.
#         """
#         async for message in get_existing_messages():
#             yield message

#         last_id = await get_last_message_id()

#         # Continuously check for new messages
#         while True:
#             new_messages = Message.objects.filter(id__gt=last_id, project__id = id).order_by('created_at').values(
#                 'id', 'user', 'content'
#             )
#             async for message in new_messages:
#                 yield f"data: {json.dumps(message)}\n\n"
#                 last_id = message['id']
#             await asyncio.sleep(0.1)  # Adjust sleep time as needed to reduce db queries.

#     async def get_existing_messages() -> AsyncGenerator:
#         messages = Message.objects.filter(project__id=project_id).order_by('created_at').values(
#             'id', 'user', 'content'
#         )
#         async for message in messages:
#             yield f"data: {json.dumps(message)}\n\n"

#     async def get_last_message_id() -> int:
#         last_message = await Message.objects.filter(project__id=project_id).alast()
#         return last_message.id if last_message else 0

#     return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

import mimetypes # https://docs.python.org/3/library/mimetypes.html

def view_file(request, project_name, id, file_name):
    # get the project based on the project name and ID
    project = get_object_or_404(Project, id=id, name=project_name)

    is_project_owner = project.owner == request.user
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    if request.user in project.members.all():
        is_project_member = request.user

    # check if the user is the project owner or PMA Administrator or a member of the project
    if is_project_owner or is_pma_admin or is_project_member:
        # fetch file from AWS S3
        s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
        bucket_name = AWS_STORAGE_BUCKET_NAME
        file_key = f"{project_name}/{file_name}"

        # determine the media type of the file, return type is (type, encoding), ignore encoding
        mime_type, _ = mimetypes.guess_type(file_name)

        # need to accept .txt, .pdf, .jpg, and other types if desired

        # generate the file's presigned URL for viewing, with correct media type
        # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/generate_presigned_url.html
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object.html

        if mime_type not in ['image/jpeg', 'text/plain', 'application/pdf']:
            disposition_type = 'attachment'  # to download the file
        else:
            disposition_type = 'inline'  # to display the file

        file_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_key,
                # makes sure the browser is able to handle the display the correct media type
                'ResponseContentType': mime_type,
                'ResponseContentDisposition': disposition_type
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )

        context = {
            'file_name': file_name,
            'file_url': file_url,
            'project': project,
        }
        return render(request, 'view_file.html', context)

    else:
        # if user doesn't have permission, show an error message
        messages.error(request, "You don't have permission to view this file.")
        return redirect('project_view', project_name=project.name, id=project.id)