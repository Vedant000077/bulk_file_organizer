import os
import shutil
import zipfile
import json
from uuid import uuid4
from pathlib import Path
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import FileResponse, JsonResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, Count, Q
from django.utils.timezone import now
from django.conf import settings

from .models import UserProfile, CustomRule, UploadJob, FileRecord
from .forms import UploadForm, RuleForm


EXT_MAP = {
    'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico'],
    'documents': ['.pdf', '.doc', '.docx', '.txt', '.odt', '.rtf', '.xlsx', '.csv'],
    'videos': ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'],
    'audio': ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.wma'],
    'archives': ['.zip', '.tar', '.gz', '.rar', '.7z', '.bz2'],
    'code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.go', '.rs'],
    'media': ['.psd', '.ai', '.sketch', '.fig'],
}


def _ensure_workspace(user):
    """Create or get user's workspace directory."""
    base = Path(settings.MEDIA_ROOT) / f'users/{user.id}'
    (base / 'uploads').mkdir(parents=True, exist_ok=True)
    (base / 'organized').mkdir(parents=True, exist_ok=True)
    (base / 'jobs').mkdir(parents=True, exist_ok=True)
    return base


def _classify(filename):
    """Auto-classify file by extension."""
    ext = Path(filename).suffix.lower()
    for cat, exts in EXT_MAP.items():
        if ext in exts:
            return cat
    return 'others'


def _format_size(size_bytes):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# === Auth Views ===
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not username or not email or not password:
            return render(request, 'organizer/register.html', {'error': 'All fields required'})
        
        if password != password_confirm:
            return render(request, 'organizer/register.html', {'error': 'Passwords do not match'})
        
        if User.objects.filter(username=username).exists():
            return render(request, 'organizer/register.html', {'error': 'Username already taken'})
        
        user = User.objects.create_user(username=username, email=email, password=password)
        UserProfile.objects.create(user=user)
        login(request, user)
        return redirect('dashboard')
    
    return render(request, 'organizer/register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'organizer/login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'organizer/login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# === Dashboard & Jobs ===
@login_required
def dashboard(request):
    """User dashboard with job history and stats."""
    try:
        profile = request.user.profile
    except:
        profile = UserProfile.objects.create(user=request.user)
    
    all_jobs = UploadJob.objects.filter(user=request.user).order_by('-created_at')
    completed_jobs = all_jobs.filter(status='completed')[:10]
    
    stats = {
        'total_jobs': all_jobs.count(),
        'completed_jobs': all_jobs.filter(status='completed').count(),
        'total_files': sum(j.total_files for j in all_jobs),
        'total_space': _format_size(sum(j.total_size for j in all_jobs)),
    }
    
    return render(request, 'organizer/dashboard.html', {
        'jobs': completed_jobs,
        'stats': stats,
        'profile': profile,
    })


@login_required
def upload(request):
    """Upload files and create a new job."""
    workspace = _ensure_workspace(request.user)
    error = None
    
    if request.method == 'POST':
        # Don't validate files field since we handle it manually
        files = request.FILES.getlist('files')
        job_name = request.POST.get('job_name', '').strip() or 'Untitled Job'
        rename_pattern = request.POST.get('rename_pattern', '').strip() or '{index}_{name}'
        
        if not files or len(files) == 0:
            error = 'Please select at least one file to upload.'
            form = UploadForm()
            return render(request, 'organizer/upload.html', {'form': form, 'error': error})
        
        try:
            # Create job
            total_size = sum(f.size for f in files)
            job = UploadJob.objects.create(
                user=request.user,
                job_name=job_name,
                status='pending',
                total_files=len(files),
                total_size=total_size,
            )
            
            # Save uploaded files
            updir = workspace / 'uploads' / str(job.id)
            updir.mkdir(parents=True, exist_ok=True)
            file_data = []
            
            for f in files:
                safe_name = f.name.replace('\\', '/').split('/')[-1]
                dest = updir / safe_name
                file_size = 0
                
                with open(dest, 'wb+') as out:
                    for chunk in f.chunks():
                        out.write(chunk)
                        file_size += len(chunk)
                
                category = _classify(safe_name)
                file_data.append({
                    'original_name': safe_name,
                    'category': category,
                    'file_size': file_size,
                })
            
            if not file_data:
                job.delete()
                error = 'No files were saved successfully.'
                return render(request, 'organizer/upload.html', {'form': form, 'error': error})
            
            # Store in session for preview
            request.session['current_job_id'] = job.id
            request.session['file_data'] = file_data
            request.session['rename_pattern'] = rename_pattern
            request.session.modified = True
            
            return redirect('preview')
        except Exception as e:
            print(f"Upload error: {e}")
            error = f'Upload failed: {str(e)}'
            form = UploadForm()
            return render(request, 'organizer/upload.html', {'form': form, 'error': error})
    else:
        form = UploadForm()
    
    return render(request, 'organizer/upload.html', {'form': form})


@login_required
def preview(request):
    """Preview file organization before applying."""
    job_id = request.session.get('current_job_id')
    file_data = request.session.get('file_data', [])
    pattern = request.session.get('rename_pattern', '{index}_{name}')
    
    if not job_id or not file_data:
        return redirect('upload')
    
    job = get_object_or_404(UploadJob, id=job_id, user=request.user)
    
    # Generate preview with new names
    preview_list = []
    for idx, item in enumerate(file_data, start=1):
        try:
            new_name = pattern.format(index=idx, name=item['original_name'])
        except KeyError:
            new_name = f"{idx}_{item['original_name']}"
        
        preview_list.append({
            **item,
            'index': idx,
            'new_name': new_name,
        })
    
    request.session['preview'] = preview_list
    request.session.modified = True
    
    return render(request, 'organizer/preview.html', {
        'job': job,
        'preview': preview_list,
        'pattern': pattern,
    })


@login_required
@require_POST
def organize(request):
    """Apply organization and create ZIP."""
    job_id = request.session.get('current_job_id')
    preview_list = request.session.get('preview', [])
    
    if not job_id:
        print("No job_id in session")
        return redirect('upload')
    
    if not preview_list:
        print("No preview_list in session")
        return redirect('upload')
    
    try:
        job = get_object_or_404(UploadJob, id=job_id, user=request.user)
        workspace = _ensure_workspace(request.user)
        
        updir = workspace / 'uploads' / str(job.id)
        orgdir = workspace / 'jobs' / str(job.id)
        orgdir.mkdir(parents=True, exist_ok=True)
        
        print(f"Organizing job {job.id}")
        print(f"Source dir: {updir}")
        print(f"Org dir: {orgdir}")
        
        # Move and organize files
        successfully_moved = 0
        for item in preview_list:
            cat = item['category']
            target_dir = orgdir / cat
            target_dir.mkdir(parents=True, exist_ok=True)
            
            src = updir / item['original_name']
            dest = target_dir / item['new_name']
            
            if src.exists():
                try:
                    print(f"Copying {src} to {dest}")
                    shutil.copy2(str(src), str(dest))
                    FileRecord.objects.create(
                        job=job,
                        original_name=item['original_name'],
                        new_name=item['new_name'],
                        category=cat,
                        file_size=item.get('file_size', src.stat().st_size),
                        original_path=str(src),
                        organized_path=str(dest),
                    )
                    successfully_moved += 1
                except Exception as e:
                    print(f"Error copying file {item['original_name']}: {e}")
            else:
                print(f"Source file not found: {src}")
        
        print(f"Successfully moved {successfully_moved} files")
        
        # Create ZIP
        zip_path = workspace / 'jobs' / f'{job.id}.zip'
        if zip_path.exists():
            zip_path.unlink()
        
        print(f"Creating ZIP at {zip_path}")
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(str(orgdir)):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, str(orgdir))
                        zf.write(full, arc)
            print(f"ZIP created successfully")
        except Exception as e:
            print(f"Error creating ZIP: {e}")
        
        # Update job
        job.status = 'completed'
        job.processed_files = successfully_moved
        job.completed_at = now()
        job.save()
        print(f"Job {job.id} marked as completed")
        
        # Update profile stats
        try:
            profile = request.user.profile
            profile.total_files_organized += job.total_files
            profile.total_space_saved += job.total_size
            profile.save()
            print(f"Profile stats updated")
        except Exception as e:
            print(f"Error updating profile: {e}")
        
        # Clear session data
        request.session['current_job_id'] = None
        request.session['file_data'] = None
        request.session['preview'] = None
        request.session.modified = True
        
        return redirect('download', job_id=job.id)
    except Exception as e:
        print(f"Organize error: {e}")
        import traceback
        traceback.print_exc()
        return redirect('upload')


@login_required
def download(request, job_id):
    """Download organized files as ZIP."""
    try:
        job = get_object_or_404(UploadJob, id=job_id, user=request.user)
        workspace = _ensure_workspace(request.user)
        zip_path = workspace / 'jobs' / f'{job.id}.zip'
        
        print(f"Download request for job {job.id}")
        print(f"ZIP path: {zip_path}")
        print(f"ZIP exists: {zip_path.exists()}")
        
        if not zip_path.exists():
            print(f"ZIP not found at {zip_path}")
            raise Http404('Archive not available')
        
        safe_filename = f'{job.job_name.replace(" ", "_")}.zip'
        
        response = FileResponse(
            open(zip_path, 'rb'),
            as_attachment=True,
            filename=safe_filename,
            content_type='application/zip'
        )
        response['Content-Length'] = zip_path.stat().st_size
        return response
    except Http404:
        raise
    except Exception as e:
        print(f"Download error: {e}")
        import traceback
        traceback.print_exc()
        raise Http404('Error preparing download')


@login_required
def job_detail(request, job_id):
    """View job details and file records."""
    job = get_object_or_404(UploadJob, id=job_id, user=request.user)
    files = job.files.all()
    
    return render(request, 'organizer/job_detail.html', {
        'job': job,
        'files': files,
    })


# === Rules Management ===
@login_required
def rules(request):
    """Manage custom organization rules."""
    rules_list = CustomRule.objects.filter(user=request.user)
    
    if request.method == 'POST':
        form = RuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.user = request.user
            rule.save()
            return redirect('rules')
    else:
        form = RuleForm()
    
    return render(request, 'organizer/rules.html', {
        'rules': rules_list,
        'form': form,
    })


@login_required
def delete_rule(request, rule_id):
    """Delete a custom rule."""
    rule = get_object_or_404(CustomRule, id=rule_id, user=request.user)
    rule.delete()
    return redirect('rules')


def index(request):
    """Redirect to appropriate page."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')
