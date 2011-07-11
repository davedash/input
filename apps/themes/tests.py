from django.conf import settings

import test_utils
from elasticutils.tests import ESTestCase
from mock import Mock, patch
from nose.tools import eq_
from pyquery import PyQuery as pq
from slugify import slugify

import input
from feedback.cron import populate
from feedback.models import Opinion
from input.urlresolvers import reverse
from themes import views
from themes.utils import cluster_key

factory = test_utils.RequestFactory()
dummy_request = factory.get('/')


def test_get_sentiments():
    s = views._get_sentiments(dummy_request, 'happy')
    eq_(len(s), 4)


def test_get_products():
    s = views._get_products(dummy_request, 'firefox')
    eq_(len(s), 2)


def test_get_platforms():
    q = Mock()
    q.get_facet = lambda x: dict(linux=1, all=2, winxp=3)
    s = views._get_platforms(dummy_request, 'firefox', 'all', q)
    eq_(len(s), 3)


def test_process_filters():
    filters = {'a': 'b'}
    r = views._process_filters(filters)
    eq_(r, {'term': {'a': 'b'}})
    filters['c'] = 'd'
    r = views._process_filters(filters)
    eq_(r, {'and': [{'term': {'a': 'b'}}, {'term': {'c': 'd'}}]})


class ThemeTest(test_utils.TestCase):
    def test_basic(self):
        t = views.Theme('a', 'b', 'happy', 'firefox', 'e', version='4.0')
        eq_(t.opinions, [])

        eq_(t.get_absolute_url(), '/en-US/theme/happy/firefox/4.0/e/a')

    def test_classmethods(self):
        hits = [{"_source": {"platform": "all", "product": "firefox",
                             "version": "4.0",
                             "items": [1364806, 1350865, 1395249, 1395227],
                             "size": 4,
                             "text": "new and cool", "type": "idea",
                             "slug": "new-and-cool"}},
                {"_source": {"platform": "all", "product":
                             "firefox", "version": "4.0",
                             "items": [1480689, 1479325, 1462655, 1396188],
                             "size": 4,
                             "text": "\u0411\u044b\u0441\u0442\u0440\u0435"
                                     "\u0435 \u0438 \u043b\u0443\u0447"
                                     "\u0448\u0435!",
                             "type": "idea",
                             "slug": "\u0431\u044b\u0441\u0442\u0440\u0435"
                                     "\u0435-\u0438-\u043b\u0443\u0447"
                                     "\u0448\u0435"}}]

        themes = views.Theme.from_results(dict(hits=dict(hits=hits)))
        eq_(len(themes), 2)
        theme = views.Theme.parse_hit(hits[0], {'a': 'b'})
        eq_(theme.total, 4)


class ViewTest(ESTestCase):
    def setUp(self):
        populate(10)
        text = 'This is great'
        slug = slugify(text)
        product = input.MOBILE
        version = input.MOBILE.default_version
        platform = 'all'
        type = input.OPINION_PRAISE
        key = cluster_key(product, version, platform, type)

        data = dict(
                slug=slug,
                text=text,
                platform=platform,
                product=product.id,
                type=type.short,
                version=version,
                items=map(int, Opinion.objects.values_list('id', flat=True)),
                size=10
                )
        self.es.index(data, settings.ES_INDEX, settings.ES_TYPE_THEME,
                      id='%s-%s' % (key, slug))
        self.es.refresh()

    def test_mobile_themes(self):
        # No mobile stuff on non-mobile page.
        url = reverse('themes')
        r = self.client.get(url)
        doc = pq(r.content)
        eq_(len(doc('li.message a')), 0)

        # open the home page?mobile
        # verify that there are links
        r = self.client.get(url + '?a=mobile')
        doc = pq(r.content)
        eq_(len(doc('li.message')), 1)


class FailureTest(ESTestCase):

    def test_elastic_down(self):
        """
        Disable /themes if ES is not present.

        If ES is not present, we should get a message saying /themes is
        temporarily not available and raise a 503 error.

        In this test we put an incorrect host/port for ES_HOSTS which should be
        hillarous.
        """
        orig = settings.ES_HOSTS
        settings.__dict__['ES_HOSTS'] = ['127.0.0.1:88']
        r = self.client.get(reverse('themes'))
        eq_(r.status_code, 503)
        settings.__dict__['ES_HOSTS'] = orig

    @patch.object(settings, 'ES_DISABLED', True)
    def test_elastic_disabled(self):
        """
        Disable /themes if ES is disabled.

        If ES is disabled in this instance of Firefox Input we should
        raise a 501 Not Implemented error.
        """
        settings.__dict__['ES_DISABLED'] = True
        r = self.client.get(reverse('themes'))
        eq_(r.status_code, 501)
        settings.__dict__['ES_DISABLED'] = False
