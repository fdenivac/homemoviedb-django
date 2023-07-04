"""
Implements some specific template tags
"""
import textwrap
import pycountry

from django import template
from django.conf import settings
from django.template.defaultfilters import date as default_date_tag
import movie.utils

register = template.Library()


@register.filter
def sectoduration(value):
    """convert seconds to duration hh:mm:ss"""
    if not value:
        return "N/A"
    seconds = int(value)
    return movie.utils.seconds_tostring(seconds)


@register.filter
def smartunit(value, unit):
    """convert number in smart form : KB, MB, GB, TB"""
    if isinstance(value, str):
        value = int(value)
    return movie.utils.smart_unit(value, unit)


@register.filter
def director(team):
    "all directors on same line"
    _director = ", ".join([t.person.name for t in team.filter(job__name="Director")])
    return _director


@register.filter
def shortdate(value):
    """
    an "override" for SHORT_DATE_FORMAT :
        if settings.MY_SHORT_DATE_FORMAT is not defined, use standard localized 'SHORT_DATE_FORMAT'
    """
    fmt = getattr(settings, "MY_SHORT_DATE_FORMAT", "SHORT_DATE_FORMAT")
    return default_date_tag(value, fmt)


@register.filter(name="textwrap")
def tmpl_textwrap(value, args):
    """
    textwrap with indent
    """
    maxlen, indent = args.split(",")
    lines = textwrap.wrap(value, int(maxlen), break_long_words=False)
    result = ""
    for line in lines:
        result += f"{int(indent) * ' '}{line}\n"
    return result


@register.filter
def isolanguage(value):
    """
    iso639 to text
    """
    try:
        value = pycountry.languages.get(alpha_2=value).name
    except AttributeError:
        pass
    return value


@register.filter
def isocountries(value):
    """
    iso3166 to text
    """
    try:
        value = ", ".join(
            [
                pycountry.countries.get(alpha_2=country.strip()).name
                for country in value.split(",")
            ]
        )
    except AttributeError:
        pass
    return value


@register.filter
def notnone(value):
    """return empty value if None"""
    if value in [None, ""] or int(value) < 0:
        value = ""
    return value


@register.filter
def team_ordered(value):
    """sort movie team (value: Movie object)"""
    return value.team.all().order_by("job__name", "cast_order")


@register.filter
def tmdb_url(short_url):
    """build complete url for TMDb"""
    return f"http://image.tmdb.org/t/p/w185{short_url}"
