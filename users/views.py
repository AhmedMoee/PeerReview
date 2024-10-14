from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import Upload  
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
