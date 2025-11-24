from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload, name='upload'),
    path('preview/', views.preview, name='preview'),
    path('organize/', views.organize, name='organize'),
    path('download/<int:job_id>/', views.download, name='download'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('rules/', views.rules, name='rules'),
    path('rules/delete/<int:rule_id>/', views.delete_rule, name='delete_rule'),
]
