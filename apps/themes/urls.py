"""
/themes  - index defaults to fx/latest ver/all platforms/all feelings
/themes?product=&version=&platform=&feeling=
/theme/:pvpf/:slug
"""

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('themes.views',
    url(r'^themes/?$', 'index', name='themes'),
    url(r'^theme/(?P<sentiment>\w+)/(?P<product>\w+)/'
        '(?P<version>\d+\.?\d*\.?\d*(a|b)?\d*)/(?P<platform>\w+)/'
        '(?P<slug>.+)/?$',
        'theme', name='theme'),
)
