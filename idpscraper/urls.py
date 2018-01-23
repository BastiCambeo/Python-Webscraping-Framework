""" This file links the views to their urls """
__author__ = 'Sebastian Hofstetter'

from django.urls import path
from . import views

app_name = 'idpscraper'
urlpatterns = [
    path('', views.index, name='index'),
    path('task/<name>', views.task, name='task'),
    path('console', views.console, name='console'),
    path('export_task/<name>.txt', views.export_task, name='export_task'),
    path('save_task/<name>', views.save_task, name='save_task'),
    path('delete_task/<name>', views.delete_task, name='delete_task'),
    path('export_excel/<name>.xlsx', views.export_excel, name='export_excel'),
    path('run_task/<name>', views.run_task, name='run_task'),
    path('run_command', views.run_command, name='run_command'),
    path('new_task', views.new_task, name='new_task'),
    path('delete_results/<name>', views.delete_results, name='delete_results'),
    path('test_task/<name>', views.test_task, name='test_task'),
    path('get_task_selectors/<name>', views.get_task_selectors, name='get_task'),

    path('apartment_settings', views.apartment_settings, name='apartment_settings'),
    path('save_apartment_settings', views.save_apartment_settings, name='save_apartment_settings'),
    path('run_apartment_settings', views.run_apartment_settings, name='run_apartment_settings'),
]