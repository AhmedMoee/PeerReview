from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import Upload, JoinRequest, Project
from .forms import FileUploadForm
from .forms import ProjectForm

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
