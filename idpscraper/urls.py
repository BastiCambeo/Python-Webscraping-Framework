""" This file links the views to their urls """
__author__ = 'Sebastian Hofstetter'

from django.conf.urls import url

from idpscraper import views, idp_views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^task/([^/]+)$', views.task, name='task'),
    url(r'^console$', views.console, name='console'),
    url(r'^export_task/([^.]+).txt', views.export_task, name='export_task'),
    url(r'^save_task/([^/]+)', views.save_task, name='save_task'),
    url(r'^delete_task/([^/]+)', views.delete_task, name='delete_task'),
    url(r'^export_excel/([^/]+).xlsx', views.export_excel, name='export_excel'),
    url(r'^run_task/([^/]+)', views.run_task, name='run_task'),
    url(r'^run_command', views.run_command, name='run_command'),
    url(r'^new_task', views.new_task, name='new_task'),
    url(r'^delete_results/([^/]+)', views.delete_results, name='delete_results'),
    url(r'^test_task/([^/]+)', views.test_task, name='test_task'),
    url(r'^get_task_selectors/([^/]+)', views.get_task_selectors, name='get_task'),


    url(r'^test$', idp_views.test, name='test'),
    url(r'^injuries_in_player_seasons', idp_views.injuries_in_player_seasons, name='injuries_in_player_seasons'),
    url(r'^injuries_in_action', idp_views.injuries_in_action, name='injuries_in_action'),
    url(r'^injuries_synonymes', idp_views.injuries_synonymes, name='injuries_synonymes'),
    url(r'^relative_age_athletics', idp_views.relative_age_athletics, name='relative_age_athletics'),
    url(r'^relative_age_football', idp_views.relative_age_football, name='relative_age_football'),
    url(r'^put_tasks', idp_views.put_tasks, name='put_tasks'),
]