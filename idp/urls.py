from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic.base import RedirectView

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url='/idpscraper/'), name='home'),
    url(r'^idpscraper/', include('idpscraper.urls', namespace="idpscraper")),
    url(r'^admin/', include(admin.site.urls)),
)
