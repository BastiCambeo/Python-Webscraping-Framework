""" Apartment Settings """
__author__ = 'Sebastian Hofstetter'

from django.db import models


class ApartmentSettings(models.Model):
    """Apartment Settings """
    id = models.TextField(primary_key=True, default="global", editable=False)
    email_to = models.TextField()
    email_from = models.TextField()
    password = models.TextField()
    smtp_server = models.TextField()
    smtp_port = models.IntegerField(default=465)
    fetch_intervall = models.IntegerField(default=60)
    last_update = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def get():
        """ Fetch global Apartment Settings """
        if not ApartmentSettings.objects.all():
            ApartmentSettings().save()
        return ApartmentSettings.objects.get(pk="global")
