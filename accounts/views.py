from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import SignUpForm, LoginForm, UserUpdateForm, ProfileUpdateForm


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('devices:dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Save extra profile data
            phone = form.cleaned_data.get('phone_number')
            if phone:
                user.profile.phone_number = phone
                user.profile.save()

            messages.success(request, 'Registration successful! You can now log in.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('devices:admin_dashboard')
        return redirect('devices:dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                
                # ── SMART REDIRECT ──
                if user.is_superuser or user.is_staff:
                    return redirect('devices:admin_dashboard')
                return redirect('devices:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'accounts/profile.html', context)