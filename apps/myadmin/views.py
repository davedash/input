from django.contrib import admin
from django.views import debug

import jingo

import api.tasks


@admin.site.admin_view
def export_tsv(request):
    if request.method == 'POST':
        api.tasks.export_tsv.delay()
        data = {'exporting': True}
    else:
        data = {}

    return jingo.render(request, 'myadmin/export_tsv.html', data)


@admin.site.admin_view
def settings(request):
    settings_dict = debug.get_safe_settings()

    return jingo.render(request, 'myadmin/settings.html',
                        {'settings_dict': settings_dict})
