from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('verify/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('auth/google/', views.google_auth_callback, name='google_auth'),
    path('upload/', views.upload_dataset, name='upload'),
    path('configure/<int:dataset_id>/', views.configure_dataset, name='configure'),
    path('sample/', views.load_sample_data, name='load_sample'),
    path('dashboard/<int:dataset_id>/', views.dashboard, name='dashboard'),
    path('report/<int:dataset_id>/', views.report, name='report'),
    path('report/<int:dataset_id>/pdf/', views.export_pdf, name='export_pdf'),
    path('history/', views.history, name='history'),
    path('delete/<int:dataset_id>/', views.delete_analysis, name='delete_analysis'),
    path('api/analysis/<int:dataset_id>/', views.api_analysis_data, name='api_analysis_data'),
]
