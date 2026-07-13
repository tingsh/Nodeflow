from django import template

from apps.utils.timezones import format_site_datetime

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def site_datetime(value, site):
    return format_site_datetime(value, site)
