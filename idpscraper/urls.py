""" This file links the views to their urls """
__author__ = 'Sebastian Hofstetter'

from django.conf.urls import url
from idpscraper import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^task/([^/]+)$', views.task, name='task'),
    url(r'^console$', views.console, name='console'),
    url(r'^export_task/([^/]+).txt', views.export_task, name='export_task'),
    url(r'^save_task/([^/]+)', views.save_task, name='save_task'),
    url(r'^delete_task/([^/]+)', views.delete_task, name='delete_task'),
    url(r'^export_excel/([^/]+).xlsx', views.export_excel, name='export_excel'),
    url(r'^run_task/([^/]+)', views.run_task, name='run_task'),
    url(r'^run_command', views.run_command, name='run_command'),
    url(r'^new_task', views.new_task, name='new_task'),
    url(r'^delete_results/([^/]+)', views.delete_results, name='delete_results'),
    url(r'^test_task/([^/]+)', views.test_task, name='test_task'),
    url(r'^get_task_selectors/([^/]+)', views.get_task_selectors, name='get_task'),

    url(r'^apartment_settings', views.apartment_settings, name='apartment_settings'),
    url(r'^save_apartment_settings', views.save_apartment_settings, name='save_apartment_settings'),
]