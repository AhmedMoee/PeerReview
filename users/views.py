from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F
from django.http import HttpRequest, StreamingHttpResponse, HttpResponse, JsonResponse, HttpResponseBadRequest
from .models import Upload, JoinRequest, Project, Message, User, UserProfile
from .forms import FileUploadForm, ProjectForm, UserProfileForm, UploadMetaDataForm
from typing import AsyncGenerator
import asyncio
import json
import random
from datetime import datetime
import time
import uuid
from django.http import JsonResponse, HttpResponseRedirect
from urllib.parse import urlparse

from mysite.settings import AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME
import boto3

def login_view(request):
    # Automatically redirect users to Google login
    return redirect('socialaccount_login', provider='google')

def logout_view(request):
    logout(request)
    return redirect('/')

def dashboard(request):
    projects = Project.objects.all()
    if request.user.is_authenticated:

        # look for first name, if it doesn't exist, use their username
        user_name = request.user.first_name or request.user.username

        if request.user.groups.filter(name='PMA Administrators').exists():
            # Render the PMA Administrator dashboard
            return pma_dashboard(request)
        else:
            # Render the Common User dashboard
            return common_dashboard(request)
    # if not authenticated, anon user, redirect to home page (with Google login option)
    return anonymous_dashboard(request)
    
@login_required
def common_dashboard(request):
    user_name = request.user.first_name or request.user.username
    owned_projects = Project.objects.filter(owner=request.user)
    member_projects = Project.objects.filter(members=request.user).exclude(owner=request.user)

    return render(request, 'common_dashboard.html', {
        'user_name': user_name,
        'owned_projects': owned_projects,
        'member_projects': member_projects,
    })
    
#display project list helper method    
def get_projects_context(request):
    projects = Project.objects.all()
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    sort_by = request.GET.get('sort', '-created_at')
    
    if sort_by == 'due_date':
        projects = projects.order_by(F('due_date').asc(nulls_last=True))
    elif sort_by == '-due_date':
        projects = projects.order_by('-due_date')
    elif sort_by == 'created_at':
        projects = projects.order_by('created_at')
    elif sort_by == '-created_at':
        projects = projects.order_by('-created_at')

    search_query = request.GET.get('q', '')
    if search_query:
        projects = projects.filter(
            Q(description__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    return {
        'projects': projects,
        'sort_by': sort_by,
        'is_pma_admin': is_pma_admin
    }

@login_required
def pma_dashboard(request):
    user_name = request.user.first_name or request.user.username
    context = get_projects_context(request)
    context['user_name'] = user_name
    return render(request, 'pma_admin_dashboard.html', context)

def anonymous_dashboard(request):
    context = get_projects_context(request)
    return render(request, 'anonymous_dashboard.html', context)

@login_required
def settings(request):
    return render(request, 'settings.html')

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            project.members.add(request.user)
            return redirect('project_list')
    else:
        form = ProjectForm()

    return render(request, 'create_project.html', {'form': form})


def project_list(request):
    projects = Project.objects.all()
    project_status = {}

    # Check if the user is a PMA Administrator
    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by == 'due_date' :
        projects = projects.order_by(F('due_date').asc(nulls_last=True))
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

    visible_projects = []
    project_status = {}

    for project in projects:
        # Check visibility conditions
        if not project.is_private or project.owner == request.user or request.user in project.members.all() or is_pma_admin:
            visible_projects.append(project)

            if request.user.is_authenticated and not is_pma_admin:
                if request.user in project.members.all():
                    project_status[project.id] = 'member'
                elif JoinRequest.objects.filter(user=request.user, project=project, status='pending').exists():
                    project_status[project.id] = 'pending'
                else:
                    project_status[project.id] = 'not_member'

    project_permissions = {
        project.id: project.owner == request.user or is_pma_admin
        for project in visible_projects
    }

    return render(request, 'project_list.html', {
        'projects': visible_projects,
        'sort_by': sort_by,
        'project_status': project_status,
        'is_pma_admin': is_pma_admin,
        'project_permissions': project_permissions
    })

@login_required
def request_to_join(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    # Delete previous denied requests if they exist
    JoinRequest.objects.filter(user=request.user, project=project, status='denied').delete()

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

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if request.user == project.owner:
        pending_requests = JoinRequest.objects.filter(project=project, status='pending')
    else:
        pending_requests = None

    context = {
        'project': project,
        'pending_requests': pending_requests,
    }

    return render(request, 'project_detail.html', context)

@login_required
def leave_project(request, project_id, project_name):
    project = get_object_or_404(Project, id=project_id, name=project_name)

    # check if user is a member of the project
    if request.user in project.members.all():
        # remove membership
        project.members.remove(request.user)
        # # delete join request so they can request again after leaving
        JoinRequest.objects.filter(user=request.user, project=project).delete()
        messages.success(request, 'You have successfully left the project.')
    else:
        messages.error(request, 'You are not a member of this project.')
    return redirect('project_list')

def view_project(request, project_name, id):

    # send user back to the page they came from
    referer = request.META.get('HTTP_REFERER', '/')

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
        'referer': referer,
    }

    return render(request, 'project_main_view.html', context)

@login_required
def project_upload(request, project_name, id):
    project = get_object_or_404(Project, id=id)

    if project.name.lower() != project_name.lower():
        return redirect('project_list')

    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    transcription_text = None
    job_name = None
    output_key = None

    if request.method == 'POST':
        if request.user == project.owner:
            # Handle rubric and review guidelines uploads
            if 'rubric' in request.FILES:
                project.rubric = request.FILES['rubric']
            if 'review_guidelines' in request.FILES:
                project.review_guidelines = request.FILES['review_guidelines']
            project.save()

        # General file upload
        form = FileUploadForm(request.POST, request.FILES, project=project)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)

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

                # Construct the transcription output key
                safe_project_name = project_name.replace(' ', '_')
                output_key = f"{safe_project_name}/{uploaded_file.name}-transcription.json"
                new_upload.output_key = output_key
                new_upload.save()

                # Start transcription job if the file type is supported
                file_extension = uploaded_file.name.split('.')[-1].lower()
                if file_extension in ['mp3', 'mp4', 'wav', 'flac']:
                    job_name = f"{project.name.replace(' ', '_')}-{uploaded_file.name}-{uuid.uuid4()}-transcription"
                    file_uri = f"s3://{AWS_STORAGE_BUCKET_NAME}/{project_name}/{uploaded_file.name}"
                    print(f'Starting transcription job: {job_name} for file: {file_uri}')

                    start_transcription_job(job_name, file_uri, output_key)

                    # Save the job name to the new upload
                    new_upload.transcription_job_name = job_name
                new_upload.save()

                return redirect('project_main_view', project_name=project.name, id=project.id)
            except Exception as e:
                print(f'Error uploading file: {e}')
    else:
        form = FileUploadForm()

    # Handle GET request to retrieve transcription status
    if request.method == 'GET':
        last_upload = project.uploads.last()
        if last_upload and last_upload.transcription_job_name:
            job_name = last_upload.transcription_job_name
            output_key = last_upload.output_key
            transcribe_client = boto3.client('transcribe', region_name=AWS_S3_REGION_NAME)
            transcription_text = check_transcription_job(transcribe_client, job_name, output_key)

    return render(request, 'project_upload.html', {
        'project': project,
        'form': form,
        'is_pma_admin': is_pma_admin,
        'transcription_text': transcription_text  ,
    })

@login_required
def delete_project(request, project_name, id):
    project = get_object_or_404(Project, id=id)

    is_pma_admin = request.user.groups.filter(name='PMA Administrators').exists()
    is_project_owner = project.owner == request.user

    if is_pma_admin or is_project_owner:
        s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
        bucket_name = AWS_STORAGE_BUCKET_NAME

        folder_prefix = f"{project_name}/"

        try:
            objects_to_delete = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)
            if 'Contents' in objects_to_delete:
                delete_keys = [{'Key': obj['Key']} for obj in objects_to_delete['Contents']]

                s3.delete_objects(Bucket=bucket_name, Delete={'Objects': delete_keys})

            project.delete()
            print("Successfully deleted project and its files.")
            messages.success(request, "Project and associated files deleted successfully.")
        except Exception as e:
            print(f"Error deleting project files from S3: {e}")
            messages.error(request, "An error occurred while trying to delete the project files.")

        return redirect('project_list')
    else:
        messages.error(request, f"You don't have permission to delete {project_name}.")
        return redirect('project_main_view', project_name=project.name, id=project.id)

@login_required
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

    return redirect('project_main_view', project_name=project_name, id=id)

# @login_required
# def create_message(request, project_id, user_id):
#     if request.method == 'POST':
#         content = request.POST.get('content')
#         if content:
#             user = get_object_or_404(User, id=user_id)
#             project = get_object_or_404(Project, id=project_id)
#             Message.objects.create(content=content, project=project, user=user)
#             return JsonResponse({'status': 'Message sent'})
#     return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def create_message(request, project_id):
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            project = get_object_or_404(Project, id=project_id)
            message = Message.objects.create(content=content, project=project, user=request.user)
            return JsonResponse({
                'status': 'Message sent',
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'created_at': message.created_at.isoformat(),
                    'user': {
                        'id': request.user.id,
                        'username': request.user.username
                    }
                }
            })
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
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

@login_required
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

        if mime_type not in ['image/jpeg', 'text/plain', 'application/pdf', 'video/mp4']:
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
                prompt_id = request.POST.get("prompt_id")
                prompt = get_object_or_404(Prompt, id=prompt_id)
                new_response = response_form.save(commit=False)
                new_response.prompt = prompt
                new_response.created_by = request.user
                new_response.save()
                return redirect('view_file', project_name=project_name, id=id, file_id=file_id)

        # handling metadata update submission
        elif request.method == 'POST' and 'edit_metadata' in request.POST:
            metadata_form = UploadMetaDataForm(request.POST, instance=upload)
            if metadata_form.is_valid():
                metadata_form.save()
                return redirect('view_file', project_name=project_name, id=id, file_id=file_id)
        else:
            prompt_form = PromptForm()
            response_form = PromptResponseForm()
            # have it prepopulated in case users don't want to change the name
            metadata_form = UploadMetaDataForm(instance=upload)
        # Get the transcription job name and check the transcription status
        job_name = upload.transcription_job_name
        output_key = upload.output_key
        transcribe_client = boto3.client('transcribe', region_name=AWS_S3_REGION_NAME)
        transcription_text = check_transcription_job(transcribe_client, job_name, output_key) if job_name else None

        context = {
            'file_type': mimetypes.guess_type(upload.file.name)[0],
            'upload_name': upload.name,
            'upload_file': upload.file,
            'file_url': file_url,  # Replace with actual presigned URL generation
            'file_id': file_id,
            'upload_description': upload.description,
            'upload_keywords': upload.keywords,
            'uploaded_at': upload.uploaded_at,
            'project': project,
            'prompt_form': prompt_form,
            'response_form': response_form,
            'metadata_form': metadata_form,
            'prompts': prompts,
            'transcription_text': transcription_text,
            'job_name': job_name,
        }

        return render(request, 'view_file.html', context)

    else:
        # If user doesn't have permission, show an error message
        messages.error(request, "You don't have permission to view this file.")
        return redirect('project_view', project_name=project.name, id=project.id)

@login_required
def view_profile(request, user_id):

    # sends users back to whatever page they were viewing previously (dashboard, project view page, search users page)
    referer = request.META.get('HTTP_REFERER', '/')

    # updated to allow users to view other profiles, not just their own profile
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserProfile, user=user)
    projects = Project.objects.filter(Q(owner=user) | Q(members=user)).distinct()

    return render(request, 'view_profile.html', {'user': user, 'profile': profile, 'projects': projects,
                                                 'referer': referer})

@login_required
def edit_profile(request):
    user = get_object_or_404(User, id=request.user.id)
    profile = get_object_or_404(UserProfile, user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('view_profile', user_id=user.id)
    else:
        # Prefill the form with the current data from the profile
        form = UserProfileForm(instance=profile)

    return render(request, 'edit_profile.html', {'form': form})


def start_transcription_job(job_name, file_uri, output_key):
    transcribe_client = boto3.client('transcribe', region_name=AWS_S3_REGION_NAME)
    try:
        response = transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': file_uri},
            MediaFormat='mp4',
            LanguageCode='en-US',
            OutputBucketName=AWS_STORAGE_BUCKET_NAME,
            OutputKey=output_key,
        )
        print(f'Started transcription job: {response}')
    except Exception as e:
        print(f'Error starting transcription job: {e}')


def transcribe_file(request, project_id, file_name):
    project = get_object_or_404(Project, id=project_id)

    file_extension = file_name.split('.')[-1].lower()
    if file_extension not in ['mp4', 'mp3', 'wav', 'flac']:
        return redirect('view_project', project_name=project.name, id=project_id)

    job_name = f"{project.name}-{file_name}-transcription"
    file_uri = f"s3://{AWS_STORAGE_BUCKET_NAME}/{project.name}/{file_name}"

    start_transcription_job(job_name, file_uri)

    return redirect('view_project', project_name=project.name, id=project_id)

def check_transcription_job(transcribe_client, job_name, output_key):
    """Check the status of the transcription job."""
    try:
        response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        status = response['TranscriptionJob']['TranscriptionJobStatus']

        if status == 'COMPLETED':
            s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)

            # Fetch the transcription data
            transcription_response = s3.get_object(Bucket=AWS_STORAGE_BUCKET_NAME, Key=output_key)
            transcription_data = json.loads(transcription_response['Body'].read().decode('utf-8'))

            transcription_text = transcription_data['results']['transcripts'][0]['transcript']
            print(f"Transcription completed: {transcription_text}")
            return transcription_text
        elif status == 'FAILED':
            print(f"Transcription job {job_name} failed.")
            return "Transcription failed."
        else:
            print(f"Transcription job {job_name} is still in progress. Status: {status}")
            return "Transcribing..."

    except Exception as e:
        print(f"Error checking transcription job: {e}")
        return None

def refresh_transcription_status(request, job_name, file_id):
    upload = get_object_or_404(Upload, id=file_id)

    output_key = upload.output_key

    transcribe_client = boto3.client('transcribe', region_name=AWS_S3_REGION_NAME)
    transcription_text = check_transcription_job(transcribe_client, job_name, output_key)

    response = {
        "status": "completed" if transcription_text not in ["Transcribing...", None] else transcription_text,
        "transcription": transcription_text if transcription_text not in ["Transcribing...", None] else ""
    }
    return JsonResponse(response)

@login_required
def show_all_users(request):
    # Get all users except the logged-in user
    users = User.objects.exclude(id=request.user.id)
    return render(request, 'search_users.html', {'users': users})

from .models import ProjectInvitation
@login_required
def manage_invites(request):
    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        user_id = request.POST.get('user_id')
        
        project = get_object_or_404(Project, id=project_id, owner=request.user)
        invited_user = get_object_or_404(User, id=user_id)

        # Check if user is already a member
        if project.members.filter(id=user_id).exists():
            messages.error(request, f'{invited_user.username} is already a member of this project.')
            return redirect('project_detail', project_id=project_id)

        # Check if there's already a pending invitation
        existing_invitation = ProjectInvitation.objects.filter(
            project=project,
            invited_user=invited_user,
            status='PENDING'
        ).first()

        if existing_invitation:
            messages.warning(request, f'An invitation has already been sent to {invited_user.username}.')
        else:
            ProjectInvitation.objects.create(
                project=project,
                invited_by=request.user,
                invited_user=invited_user
            )
            messages.success(request, f'Invitation sent to {invited_user.username} for project {project.name}.')

        return redirect('search_users')

@login_required
def select_project_for_invite(request, user_id):
    invited_user = get_object_or_404(User, id=user_id)
    user_projects = Project.objects.filter(owner=request.user)
    
    return render(request, 'select_project.html', {
        'invited_user': invited_user,
        'user_projects': user_projects
    })


from datetime import datetime
@login_required
def handle_invitation(request, invitation_id):
    invitation = get_object_or_404(
        ProjectInvitation,
        id=invitation_id,
        invited_user=request.user,
        status='PENDING'
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accept':
            invitation.project.members.add(request.user)
            # ProjectMembership.objects.create(
            #     user=request.user,
            #     project=invitation.project,
            #     role='MEMBER'
            # )
            invitation.status = 'ACCEPTED'
            messages.success(request, f'You have joined {invitation.project.name}.')
        elif action == 'decline':
            invitation.status = 'DECLINED'
            messages.info(request, f'You have declined the invitation to {invitation.project.name}.')
        
        invitation.response_date = datetime.now()
        invitation.save()

    return redirect('view_invites')

@login_required
def invitation_list(request):
    pending_invitations = ProjectInvitation.objects.filter(
        invited_user=request.user,
        status='PENDING'
    ).select_related('project', 'invited_by')
    
    return render(request, 'view_invites.html', {
        'pending_invitations': pending_invitations
    })


@login_required
def upvote_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    # Check if the user has already upvoted
    if request.user in project.upvoters.all():
        # If already upvoted, subtract the upvote and remove the user from upvoters
        project.upvotes -= 1
        project.upvoters.remove(request.user)
        project.save()
        return JsonResponse({'status': 'removed', 'upvotes': project.upvotes})
    else:
        # If not upvoted, add the upvote and add the user to upvoters
        project.upvotes += 1
        project.upvoters.add(request.user)
        project.save()
        return JsonResponse({'status': 'added', 'upvotes': project.upvotes})

def popular_projects(request):
    projects = Project.objects.all().order_by('-upvotes')  

    s3 = boto3.client('s3', region_name=AWS_S3_REGION_NAME)
    bucket_name = AWS_STORAGE_BUCKET_NAME

    for project in projects:
        project.latest_upload = Upload.objects.filter(project=project).order_by('-uploaded_at').first()

        if project.latest_upload:
            upload = project.latest_upload
            file_key = f"{project.name}/{upload.file}"  

            mime_type, _ = mimetypes.guess_type(file_key)

            if mime_type not in ['image/jpeg', 'text/plain', 'application/pdf', 'video/mp4']:
                disposition_type = 'attachment'
            else:
                disposition_type = 'inline'

            file_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_key,
                    'ResponseContentType': mime_type,
                    'ResponseContentDisposition': disposition_type
                },
                ExpiresIn=3600
            )

            upload.signed_url = file_url
            file_type, _ = mimetypes.guess_type(project.latest_upload.file.name)
            project.latest_upload.file_type = file_type
        
    return render(request, 'popular_projects.html', {'projects': projects})
