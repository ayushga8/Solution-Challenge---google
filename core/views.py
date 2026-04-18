import json
import os
import io
import random
import string
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.template.loader import get_template
from django.views.decorators.csrf import csrf_exempt
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import Dataset, AnalysisResult, FairnessMetric
from .forms import DatasetUploadForm, SignUpForm
from .analysis import run_full_analysis, parse_csv_data, detect_protected_attributes, detect_target_column
from .firebase_config import FIREBASE_CONFIG, FIREBASE_PROJECT_ID


def index(request):
    """Landing page with hero, features, and upload section."""
    recent_analyses = AnalysisResult.objects.select_related('dataset').order_by('-created_at')
    if request.user.is_authenticated:
        recent_analyses = recent_analyses.filter(dataset__user=request.user)
    recent_analyses = recent_analyses[:5]
    form = DatasetUploadForm()
    return render(request, 'core/index.html', {
        'form': form,
        'recent_analyses': recent_analyses,
    })


@csrf_exempt
def signup_view(request):
    """User registration page — sends OTP on signup."""
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Inactive until OTP verified
            user.save()

            # Generate and send OTP
            otp = _generate_otp()
            request.session['signup_otp'] = otp
            request.session['signup_user_id'] = user.id
            request.session['signup_email'] = user.email
            request.session['otp_created'] = str(timezone.now())

            email_sent = _send_otp_email(user.email, user.username, otp)
            if email_sent:
                messages.info(request, f'A verification code has been sent to {user.email}')
            else:
                messages.info(request, f'Verification code generated for {user.email}')
                request.session['otp_show_demo'] = True

            return redirect('verify_otp')
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {
        'form': form,
        'firebase_config': json.dumps(FIREBASE_CONFIG),
    })


@csrf_exempt
def verify_otp(request):
    """OTP verification page after signup."""
    user_id = request.session.get('signup_user_id')
    email = request.session.get('signup_email', '')
    show_demo_otp = request.session.pop('otp_show_demo', False)

    if not user_id:
        messages.error(request, 'No pending verification. Please sign up first.')
        return redirect('signup')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        stored_otp = request.session.get('signup_otp', '')
        otp_created = request.session.get('otp_created', '')

        # Check expiry
        from datetime import datetime
        if otp_created:
            created_time = datetime.fromisoformat(otp_created)
            now = timezone.now()
            diff_minutes = (now - created_time).total_seconds() / 60
            if diff_minutes > settings.OTP_EXPIRY_MINUTES:
                messages.error(request, 'OTP has expired. Please request a new one.')
                return render(request, 'core/verify_otp.html', {'email': email})

        if entered_otp == stored_otp:
            # Activate user and log in
            try:
                user = User.objects.get(id=user_id)
                user.is_active = True
                user.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                # Clean up session
                for key in ['signup_otp', 'signup_user_id', 'signup_email', 'otp_created']:
                    request.session.pop(key, None)

                messages.success(request, f'Welcome, {user.username}! Your email has been verified.')
                return redirect('index')
            except User.DoesNotExist:
                messages.error(request, 'Account not found. Please sign up again.')
                return redirect('signup')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')

    # Show OTP on page ONLY when email delivery failed
    demo_otp = request.session.get('signup_otp', '') if show_demo_otp else None

    return render(request, 'core/verify_otp.html', {
        'email': email,
        'demo_otp': demo_otp,
    })


def resend_otp(request):
    """Resend OTP to the user's email."""
    user_id = request.session.get('signup_user_id')
    email = request.session.get('signup_email', '')

    if not user_id or not email:
        messages.error(request, 'No pending verification.')
        return redirect('signup')

    try:
        user = User.objects.get(id=user_id)
        otp = _generate_otp()
        request.session['signup_otp'] = otp
        request.session['otp_created'] = str(timezone.now())

        _send_otp_email(email, user.username, otp)
        messages.success(request, f'A new verification code has been sent to {email}')
    except User.DoesNotExist:
        messages.error(request, 'Account not found.')
        return redirect('signup')

    return redirect('verify_otp')



@csrf_exempt
def login_view(request):
    """User login page."""
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {
        'form': form,
        'firebase_config': json.dumps(FIREBASE_CONFIG),
    })


def logout_view(request):
    """Log the user out."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('index')


@csrf_exempt
def google_auth_callback(request):
    """Handle Firebase Google Sign-In — create/login Django user from Firebase data."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        # Accept both JSON body (fetch) and form POST (redirect)
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = json.loads(request.body)
        else:
            data = request.POST

        email = data.get('email', '')
        name = data.get('name', '')
        uid = data.get('uid', '')

        if not email:
            return JsonResponse({'error': 'No email provided'}, status=400)

        # Create or get user by email
        base_username = email.split('@')[0]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=name.split(' ')[0] if name else '',
                last_name=' '.join(name.split(' ')[1:]) if name and len(name.split(' ')) > 1 else '',
            )
            user.set_unusable_password()
            user.save()

        # Ensure user is active
        if not user.is_active:
            user.is_active = True
            user.save()

        # SUPERUSER BYPASS FOR DEVELOPER
        if email == 'garg.ayush18542@gmail.com':
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                user.save()

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        # Form POST → redirect; JSON → return JSON
        if 'application/json' in content_type:
            return JsonResponse({'success': True, 'username': user.username, 'redirect': '/'})
        else:
            messages.success(request, f'Welcome, {user.first_name or user.username}! Signed in with Google.')
            return redirect('index')

    except Exception as e:
        import traceback
        traceback.print_exc()
        if 'application/json' in (request.content_type or ''):
            return JsonResponse({'error': str(e)}, status=500)
        else:
            messages.error(request, f'Google Sign-In failed: {str(e)}')
            return redirect('login')




def upload_dataset(request):
    """Handle CSV file upload — saves dataset and redirects to column selector."""
    if request.method == 'POST':
        form = DatasetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dataset = form.save(commit=False)
            if request.user.is_authenticated:
                dataset.user = request.user

            # Read file content
            uploaded_file = request.FILES['file']
            file_content = uploaded_file.read().decode('utf-8-sig')
            uploaded_file.seek(0)

            # Save dataset
            dataset.save()

            # Parse and store metadata
            rows, columns = parse_csv_data(file_content)
            dataset.row_count = len(rows)
            dataset.column_count = len(columns)
            dataset.columns = columns
            protected = detect_protected_attributes(columns)
            dataset.protected_attributes = protected
            target = detect_target_column(columns)
            dataset.target_column = target
            dataset.save()

            # Redirect to column selector for user to confirm/edit
            return redirect('configure', dataset_id=dataset.id)
        else:
            return render(request, 'core/index.html', {'form': form, 'errors': form.errors})

    return redirect('index')


def configure_dataset(request, dataset_id):
    """Column selector — let user confirm/edit protected attributes and target column."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    columns = dataset.columns
    auto_protected = dataset.protected_attributes
    auto_target = dataset.target_column

    if request.method == 'POST':
        # Get user selections
        selected_protected = request.POST.getlist('protected_attributes')
        selected_target = request.POST.get('target_column', '')

        # Update dataset
        dataset.protected_attributes = selected_protected
        dataset.target_column = selected_target if selected_target else None
        dataset.save()

        # Read file and run analysis
        file_content = dataset.file.read().decode('utf-8-sig')
        dataset.file.seek(0)

        results = run_full_analysis(file_content, selected_protected, selected_target if selected_target else None)

        # Delete existing analysis if re-running
        AnalysisResult.objects.filter(dataset=dataset).delete()

        # Save analysis result
        analysis = AnalysisResult.objects.create(
            dataset=dataset,
            overall_severity=results.get('severity', 'medium'),
            overall_score=results.get('overall_score', 0),
            summary=f"Analysis of {dataset.name}: {results.get('severity', 'unknown')} bias detected with fairness score {results.get('overall_score', 0)}",
            recommendations_json=json.dumps(results.get('recommendations', [])),
            detailed_results_json=json.dumps(results.get('metrics', {}), default=str),
        )

        # Save individual metrics
        _save_metrics(analysis, results.get('metrics', {}))

        dataset.is_analyzed = True
        dataset.save()

        return redirect('dashboard', dataset_id=dataset.id)

    return render(request, 'core/configure.html', {
        'dataset': dataset,
        'columns': columns,
        'auto_protected': auto_protected,
        'auto_target': auto_target,
    })


def load_sample_data(request):
    """Load the built-in sample dataset for demo purposes."""
    sample_path = os.path.join(settings.BASE_DIR, 'sample_data', 'loan_data.csv')

    if not os.path.exists(sample_path):
        return redirect('index')

    with open(sample_path, 'r', encoding='utf-8-sig') as f:
        file_content = f.read()

    from django.core.files.base import ContentFile

    dataset = Dataset.objects.create(
        name='Sample: Loan Approval Dataset',
        user=request.user if request.user.is_authenticated else None,
    )
    dataset.file.save('sample_loan_data.csv', ContentFile(file_content.encode('utf-8')))

    rows, columns = parse_csv_data(file_content)
    protected = detect_protected_attributes(columns)
    target = detect_target_column(columns)

    dataset.row_count = len(rows)
    dataset.column_count = len(columns)
    dataset.columns = columns
    dataset.protected_attributes = protected
    dataset.target_column = target
    dataset.save()

    results = run_full_analysis(file_content, protected, target)

    analysis = AnalysisResult.objects.create(
        dataset=dataset,
        overall_severity=results.get('severity', 'medium'),
        overall_score=results.get('overall_score', 0),
        summary=f"Sample analysis: {results.get('severity', 'unknown')} bias detected",
        recommendations_json=json.dumps(results.get('recommendations', [])),
        detailed_results_json=json.dumps(results.get('metrics', {}), default=str),
    )

    _save_metrics(analysis, results.get('metrics', {}))

    dataset.is_analyzed = True
    dataset.save()

    return redirect('dashboard', dataset_id=dataset.id)


def dashboard(request, dataset_id):
    """Main analysis dashboard showing all metrics and visualizations."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    analysis = get_object_or_404(AnalysisResult, dataset=dataset)
    metrics = analysis.metrics.all()

    metrics_by_attr = {}
    for m in metrics:
        if m.protected_attribute not in metrics_by_attr:
            metrics_by_attr[m.protected_attribute] = []
        metrics_by_attr[m.protected_attribute].append({
            'type': m.metric_type,
            'type_display': m.get_metric_type_display(),
            'value': m.value,
            'threshold': m.threshold,
            'status': m.status,
            'details': m.details,
        })

    # Build intersectional analysis data
    detailed = analysis.detailed_results
    intersectional_data = _build_intersectional_data(detailed)

    context = {
        'dataset': dataset,
        'analysis': analysis,
        'metrics': metrics,
        'metrics_by_attr': metrics_by_attr,
        'detailed_results': detailed,
        'recommendations': analysis.recommendations,
        'metrics_json': json.dumps(metrics_by_attr, default=str),
        'detailed_results_json': json.dumps(detailed, default=str),
        'intersectional_json': json.dumps(intersectional_data, default=str),
    }
    return render(request, 'core/dashboard.html', context)


def report(request, dataset_id):
    """Generate a printable/downloadable audit report."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    analysis = get_object_or_404(AnalysisResult, dataset=dataset)
    metrics = analysis.metrics.all()

    metrics_by_attr = {}
    for m in metrics:
        if m.protected_attribute not in metrics_by_attr:
            metrics_by_attr[m.protected_attribute] = []
        metrics_by_attr[m.protected_attribute].append({
            'type': m.metric_type,
            'type_display': m.get_metric_type_display(),
            'value': m.value,
            'threshold': m.threshold,
            'status': m.status,
        })

    context = {
        'dataset': dataset,
        'analysis': analysis,
        'metrics_by_attr': metrics_by_attr,
        'recommendations': analysis.recommendations,
    }
    return render(request, 'core/report.html', context)


def export_pdf(request, dataset_id):
    """Generate and download a PDF audit report."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    analysis = get_object_or_404(AnalysisResult, dataset=dataset)
    metrics = analysis.metrics.all()

    metrics_by_attr = {}
    for m in metrics:
        if m.protected_attribute not in metrics_by_attr:
            metrics_by_attr[m.protected_attribute] = []
        metrics_by_attr[m.protected_attribute].append({
            'type': m.metric_type,
            'type_display': m.get_metric_type_display(),
            'value': m.value,
            'threshold': m.threshold,
            'status': m.status,
        })

    context = {
        'dataset': dataset,
        'analysis': analysis,
        'metrics_by_attr': metrics_by_attr,
        'recommendations': analysis.recommendations,
        'is_pdf': True,
    }

    if not pisa:
        messages.error(request, "PDF export is not supported in this environment yet due to missing system libraries. Please use the web table view or Print to PDF from your browser.")
        return redirect('report', dataset_id=dataset.id)

    template = get_template('core/report_pdf.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bias_audit_{dataset.name}.pdf"'

    try:
        pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=response)
        if pisa_status.err:
            return HttpResponse('Error generating PDF', status=500)
    except Exception as e:
        messages.error(request, f"PDF generation failed: {str(e)}")
        return redirect('report', dataset_id=dataset.id)

    return response


def history(request):
    """Show all past analyses."""
    analyses = AnalysisResult.objects.select_related('dataset').order_by('-created_at')
    if request.user.is_authenticated:
        analyses = analyses.filter(dataset__user=request.user)
    return render(request, 'core/history.html', {'analyses': analyses})


def delete_analysis(request, dataset_id):
    """Delete a dataset and its analysis."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    dataset.delete()
    return redirect('history')


def api_analysis_data(request, dataset_id):
    """API endpoint returning analysis data as JSON for chart rendering."""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    analysis = get_object_or_404(AnalysisResult, dataset=dataset)

    return JsonResponse({
        'dataset': {
            'name': dataset.name,
            'rows': dataset.row_count,
            'columns': dataset.column_count,
            'protected_attributes': dataset.protected_attributes,
            'target_column': dataset.target_column,
        },
        'overall_score': analysis.overall_score,
        'severity': analysis.overall_severity,
        'detailed_results': analysis.detailed_results,
        'recommendations': analysis.recommendations,
    })


# ==============================
# Helper Functions
# ==============================

def _save_metrics(analysis, metrics):
    """Save individual fairness metrics to the database."""
    for attr, attr_data in metrics.items():
        for metric_key in ['demographic_parity', 'disparate_impact', 'statistical_parity_difference', 'group_size_ratio']:
            metric_info = attr_data.get(metric_key, {})
            if metric_info and metric_info.get('value') is not None:
                value = metric_info['value']
                if metric_key in ('disparate_impact', 'demographic_parity'):
                    status = 'pass' if value >= 0.8 else ('warning' if value >= 0.6 else 'fail')
                    threshold = 0.8
                elif metric_key == 'statistical_parity_difference':
                    status = 'pass' if value <= 10 else ('warning' if value <= 20 else 'fail')
                    threshold = 10
                else:
                    status = 'pass' if value >= 0.5 else ('warning' if value >= 0.3 else 'fail')
                    threshold = 0.5

                FairnessMetric.objects.create(
                    analysis=analysis,
                    metric_type=metric_key,
                    protected_attribute=attr,
                    value=value,
                    threshold=threshold,
                    status=status,
                    details_json=json.dumps(metric_info.get('details', {}), default=str),
                )


def _build_intersectional_data(detailed):
    """Build intersectional analysis data from detailed results for heatmap visualization."""
    intersectional = {}

    # Build cross-attribute outcome rates for heatmap
    attrs = list(detailed.keys())
    for attr in attrs:
        outcome_rates = detailed[attr].get('outcome_rates', {})
        if outcome_rates:
            intersectional[attr] = {}
            for group, rates in outcome_rates.items():
                intersectional[attr][group] = rates.get('rate', 0)

    return intersectional


def _generate_otp():
    """Generate a random 6-digit OTP."""
    length = getattr(settings, 'OTP_LENGTH', 6)
    return ''.join(random.choices(string.digits, k=length))


def _send_otp_email(email, username, otp):
    """Send OTP verification email."""
    from django.core.mail import send_mail

    subject = f'🔐 Your Verification Code — Unbiased AI'
    message = f"""Hi {username},

Welcome to Unbiased AI Decision!

Your verification code is: {otp}

This code will expire in {getattr(settings, 'OTP_EXPIRY_MINUTES', 10)} minutes.

If you didn't create an account, please ignore this email.

— Unbiased AI Team
"""

    html_message = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f172a; border-radius: 16px; color: #e2e8f0;">
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="display: inline-block; padding: 12px; background: linear-gradient(135deg, #7c3aed, #06b6d4); border-radius: 12px; margin-bottom: 12px;">
                <span style="font-size: 24px;">🛡️</span>
            </div>
            <h1 style="font-size: 22px; font-weight: 800; color: #f1f5f9; margin: 0;">Unbiased AI Decision</h1>
        </div>
        <p style="color: #94a3b8; font-size: 14px;">Hi <strong style="color: #e2e8f0;">{username}</strong>,</p>
        <p style="color: #94a3b8; font-size: 14px;">Welcome! Use this code to verify your email:</p>
        <div style="text-align: center; margin: 28px 0;">
            <div style="display: inline-block; padding: 16px 40px; background: linear-gradient(135deg, rgba(124,58,237,0.2), rgba(6,182,212,0.2)); border: 1px solid rgba(124,58,237,0.3); border-radius: 12px;">
                <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #a78bfa;">{otp}</span>
            </div>
        </div>
        <p style="color: #64748b; font-size: 12px; text-align: center;">Code expires in {getattr(settings, 'OTP_EXPIRY_MINUTES', 10)} minutes</p>
        <hr style="border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 24px 0;">
        <p style="color: #475569; font-size: 11px; text-align: center;">If you didn't sign up, ignore this email.</p>
    </div>
    """

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"[OTP EMAIL] Failed to send to {email}: {e}")
        print(f"[OTP EMAIL] OTP for {username}: {otp}")
        return False
