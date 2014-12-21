from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponseRedirect, HttpResponse


def index(request):
    return HttpResponse(timezone.localtime(timezone.now()))