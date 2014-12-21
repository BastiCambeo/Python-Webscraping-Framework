__author__ = 'Sebastian Hofstetter'

from django.conf.urls import url

from idpscraper import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
]