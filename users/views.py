from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

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