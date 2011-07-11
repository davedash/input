import json
import logging
import urllib
from collections import defaultdict
from threading import local

_local = local()

from django.conf import settings
from django.http import Http404
from django.utils.encoding import smart_unicode

log = logging.getLogger('grouperfish')


class GF(object):

    @classmethod
    def __enter__(cls):
        if not hasattr(_local, 'gf'):
            _local.gf = GF(settings.GF_HOST, settings.GF_NAMESPACE)

        return _local.gf

    @classmethod
    def __exit__(cls, *args, **kw):
        _local.gf.force_bulk()

    def __init__(self, host, namespace):
        self.host = host
        self.namespace = namespace
        self.bulk = defaultdict(list)

    def _post_data(self, collection_key, data):
        url = '/'.join((self.host, 'collections', self.namespace,
                        collection_key))
        try:
            u = urllib.urlopen(url, data=json.dumps(data))
            return u.read()
        except IOError:
            log.warn('problem posting to %s' % url)

    def index(self, collection_key, bulk=False, **kw):
        """POST /collections/<namespace>/<collection-key>"""
        if bulk:
            self.bulk[collection_key].append(kw)
            return
        result = self._post_data(collection_key, kw)
        result = '%s%s' % (self.host, result)
        log.debug(result)
        return result

    def force_bulk(self):
        for collection_key, data in self.bulk.iteritems():
            result = self._post_data(collection_key, {'bulk': data})
            log.debug(result)
        self.bulk = defaultdict(list)

    def fetch(self, collection_key):
        url = '/'.join((self.host, 'clusters', self.namespace, collection_key))
        u = urllib.urlopen(url)
        if u.getcode() == 404:
            raise Http404
        result = smart_unicode(u.read())
        log.debug(url)
        log.debug(result)
        return json.loads(result)
