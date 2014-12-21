__author__ = 'Sebastian Hofstetter'

from django.conf.urls import url

from idpscraper import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^task/([^/]+)$', views.task, name='task'),
    url(r'^console$', views.console, name='console'),
    url(r'^relative_age$', views.relative_age, name='relative_age'),
]