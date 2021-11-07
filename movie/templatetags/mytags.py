'''
Implements some specific template tags
'''
from django import template

register = template.Library()


@register.filter
def sectoduration(value):
    ''' convert seconds to duration hh:mm:ss '''
    if not value:
        return 'N/A'
    seconds = int(value)
    return '%02d:%02d:%02d' % (seconds//3600, (seconds//60)%60, seconds%60)

@register.filter
def smartsize(value):
    ''' convert number in smart form : KB, MB, GB, TB '''
    unit = 'o'
    if isinstance(value, str):
        value = int(value)
    if value > 1000*1000*1000*1000:
        return '%.2f T%s' % (value/(1000*1000*1000*1000.), unit)
    if value > 1000*1000*1000:
        return '%.2f G%s' % (value/(1000*1000*1000.), unit)
    if value > 1000*1000:
        return '%.2f M%s' % (value/(1000*1000.), unit)
    if value > 1000:
        return '%.2f K%s' % (value/(1000.), unit)

@register.filter
def director(movie):
    ' all directors on same line'
    _director = ', '.join([t.name for t in movie.team.filter(job='Director')])
    return _director
