""" Apartment Settings """
__author__ = 'Sebastian Hofstetter'

from django.db import models


class ApartmentSettings(models.Model):
    """Apartment Settings """
    id = models.TextField(primary_key=True, default="global", editable=False)
    email = models.TextField()
    password = models.TextField()
    smtp = models.TextField()
    port = models.IntegerField(default=465)


    @staticmethod
    def get():
        """ Fetch global Apartment Settings """
        if not ApartmentSettings.objects.all():
            ApartmentSettings().save()
        return ApartmentSettings.objects.get(pk="global")
