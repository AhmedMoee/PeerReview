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
from django.http import HttpResponseBadRequest

from mysite.settings import AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME
import boto3

def home(request):
    # If the user is authenticated, redirect to the dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    # Otherwise, render the home page (with the Google login option)
    return render(request, 'home.html')
    

def dashboard(request):
    if request.user.is_authenticated:
        # look for first name, if it doesn't exist, use their username
        user_name = request.user.first_name or request.user.username

        if request.user.groups.filter(name='PMA Administrators').exists():
            # Render the PMA Administrator dashboard
            return render(request, 'pma_admin_dashboard.html', {'user_name': user_name})
        else:
            # Render the Common User dashboard
            return render(request, 'common_dashboard.html', {'user_name': user_name})
    else:
        # if not authenticated, anon user, redirect to home page (with Google login option)
        return render(request, 'home.html')

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
from django.db.models import Q, F

def project_list(request):
    projects = Project.objects.all()
    project_status = {}

    # Check if the user is a PMA Administrator
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by == 'due_date' :
        project = projects.order_by(F('due_date').asc(nulls_last=True))
    elif sort_by == '-due_date':
        projects = projects.order_by('-due_date')
    elif sort_by == 'created_at' :
        projects = projects.order_by('created_at')
    elif sort_by == '-created_at' :
        projects = projects.order_by('-created_at')
    
    search_query = request.GET.get('q', '')
    if search_query:
        projects = projects.filter(
            Q(description__icontains=search_query) | 
            Q(category__icontains=search_query)
        )


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
        'sort_by': sort_by,
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


def leave_project(request, project_id, project_name):
    project = get_object_or_404(Project, id=project_id, name=project_name)

    # check if user is a member of the project
    if request.user in project.members.all():
        # # delete join request so they can request again after leaving
        JoinRequest.objects.filter(user=request.user, project=project).delete()
        # remove membership
        project.members.remove(request.user)
        messages.success(request, 'You have successfully left the project.')
    else:
        messages.error(request, 'You are not a member of this project.')
    return redirect('project_list')


def project_uploads(request, project_name, id):
    project = get_object_or_404(Project, id=id)
    
    search_query = request.GET.get('search', '')  # Get search query from the URL

    # Filter uploads associated with the project and search query
    uploads = Upload.objects.filter(project=project)
    if search_query:
        uploads = uploads.filter(Q(name__icontains=search_query) | Q(keywords__icontains=search_query))

    is_owner_or_admin = (project.owner == request.user or request.user.groups.filter(name='PMA Administrators').exists())

    context = {
        'project': project,
        'files': uploads,
        'is_owner_or_admin': is_owner_or_admin,
    }

    return render(request, 'project_uploads.html', context)

def view_project(request, project_name, id):
    project = get_object_or_404(Project, id=id)

    if project.name.lower() != project_name.lower():  
        return redirect('project_list')
    
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()

    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES, project=project)
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

                # Save metadata to the database
                new_upload = form.save(commit=False)
                new_upload.project = project
                new_upload.file = uploaded_file.name
                new_upload.save()

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
    
def delete_file(request, project_name, id, file_id):
    project = get_object_or_404(Project, id=id, name=project_name)
    file_obj = get_object_or_404(Upload, id=file_id, project=project)

    # Check if the user has permissions to delete the file
    if project.owner == request.user or request.user.groups.filter(name='PMA Administrators').exists():
        s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
        bucket_name = AWS_STORAGE_BUCKET_NAME

        # Construct the correct S3 file key using the file metadata
        file_key = f"{project_name}/{file_obj.file}"

        try:
            # Delete the file from S3
            response = s3.delete_object(Bucket=bucket_name, Key=file_key)
            print(f"S3 deletion response: {response}")
            
            # Delete the file's metadata from the database
            file_obj.delete()

            messages.success(request, f"File '{file_obj.name}' has been deleted.")
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

import mimetypes  # https://docs.python.org/3/library/mimetypes.html
from .forms import PromptForm, PromptResponseForm
from .models import Prompt

def view_file(request, project_name, id, file_id):
    # Get the project based on the project name and ID
    project = get_object_or_404(Project, id=id, name=project_name)

    # Check user permissions
    is_project_owner = project.owner == request.user
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    is_project_member = request.user in project.members.all()

    # Get file metadata from the database using file_id
    upload = get_object_or_404(Upload, id=file_id, project=project)
    
    # Retrieve prompts and their responses
    prompts = upload.prompts.all()  # Retrieve all prompts related to this upload

    # Ensure the user is allowed to view the file
    if is_project_owner or is_pma_admin or is_project_member:
        # Fetch file from AWS S3
        s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
        bucket_name = AWS_STORAGE_BUCKET_NAME

        # Determine the S3 file key from the file_obj's path
        file_key = f"{project_name}/{upload.file}"

        # Determine the media type of the file
        mime_type, _ = mimetypes.guess_type(file_key)

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
        
        # Handle prompt form submission
        if request.method == 'POST' and 'add_prompt' in request.POST:
            prompt_form = PromptForm(request.POST)
            if prompt_form.is_valid():
                new_prompt = prompt_form.save(commit=False)
                new_prompt.upload = upload
                new_prompt.created_by = request.user
                new_prompt.save()
                return redirect('view_file', project_name=project_name, id=id, file_id=file_id)
        
        # Handle response form submission
        elif request.method == 'POST' and 'add_response' in request.POST:
            response_form = PromptResponseForm(request.POST)
            if response_form.is_valid():
                # Retrieve the prompt instance
                prompt_id = request.POST.get("prompt_id")
                prompt = get_object_or_404(Prompt, id=prompt_id)

                # Save the new response
                new_response = response_form.save(commit=False)
                new_response.prompt = prompt
                new_response.created_by = request.user
                new_response.save()
                
                return redirect('view_file', project_name=project_name, id=id, file_id=file_id)

        else:
            prompt_form = PromptForm()
            response_form = PromptResponseForm()

        context = {
            'file_type': mimetypes.guess_type(upload.file.name)[0],
            'upload_name': upload.name,
            'upload_file': upload.file,
            'file_url': file_url,  # Replace with actual presigned URL generation
            'upload_description': upload.description,
            'upload_keywords': upload.keywords,
            'uploaded_at': upload.uploaded_at,
            'project': project,
            'prompt_form': prompt_form,
            'response_form': response_form,
            'prompts': prompts,
        }
        
        return render(request, 'view_file.html', context)

    else:
        # If user doesn't have permission, show an error message
        messages.error(request, "You don't have permission to view this file.")
        return redirect('project_view', project_name=project.name, id=project.id)