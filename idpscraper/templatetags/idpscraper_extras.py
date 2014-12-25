__author__ = 'Sebastian Hofstetter'

from django import template

register = template.Library()

@register.filter
def debug(element):
    return element