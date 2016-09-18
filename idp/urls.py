from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic.base import RedirectView

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/idpscraper/'), name='home'),
    url(r'^idpscraper/', include('idpscraper.urls', namespace="idpscraper")),
    url(r'^admin/', include(admin.site.urls)),
]
