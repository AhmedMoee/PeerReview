from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import Upload, JoinRequest
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
    
@login_required
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
    return render(request, 'upload_file.html', {'form': form})

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            project.members.add(request.user)
            return redirect('dashboard')
    else:
        form = ProjectForm()

    return render(request, 'create_project.html', {'form': form})


from django.shortcuts import render
from .models import Project


@login_required
def project_list(request):
    projects = Project.objects.all()
    project_status = {}

    for project in projects:
        if request.user in project.members.all():
            project_status[project.id] = 'member'
        elif JoinRequest.objects.filter(user=request.user, project=project, status='pending').exists():
            project_status[project.id] = 'pending'
        else:
            project_status[project.id] = 'not_member'

    return render(request, 'project_list.html', {
        'projects': projects,
        'project_status': project_status
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

