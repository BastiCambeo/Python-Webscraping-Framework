from django.contrib import admin
from idpscraper.models import Task, Result, UrlSelector, Selector

admin.site.register(Task)
admin.site.register(Result)
admin.site.register(UrlSelector)
admin.site.register(Selector)