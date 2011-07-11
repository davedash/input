from collections import namedtuple

from django import http
from django.conf import settings
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.utils.encoding import iri_to_uri

import jingo
from elasticutils import es_required_or_50x, get_es, S
from product_details.version_compare import version_list
from pyes.exceptions import ElasticSearchException
from tower import ugettext as _, ugettext_lazy as _lazy

import input
from feedback.models import Opinion
from input import (OPINION_PRAISE, OPINION_ISSUE, OPINION_IDEA, PRODUCTS,
                   PLATFORMS, FIREFOX, PRODUCT_USAGE)
from input.decorators import cache_page
from input.helpers import urlparams as urlparams_orig
from input.urlresolvers import reverse


Filter = namedtuple('Filter', 'url text title selected')
urlparams = lambda url, **kw: urlparams_orig(url, page=None, **kw)


def _get_sentiments(request, sentiment):
    """Get available sentiment filters."""
    sentiments = []
    url = request.get_full_path()

    f = Filter(urlparams(url, s=None), _('All'),  _('All feedback'),
               not sentiment)
    sentiments.append(f)

    f = Filter(urlparams(url, s=OPINION_PRAISE.short), _('Praise'),
               _('Praise only'), (sentiment == OPINION_PRAISE.short))
    sentiments.append(f)

    f = Filter(urlparams(url, s=OPINION_ISSUE.short), _('Issues'),
               _('Issues only'), (sentiment == OPINION_ISSUE.short))
    sentiments.append(f)

    f = Filter(urlparams(url, s=OPINION_IDEA.short), _('Ideas'),
               _('Ideas only'), (sentiment == OPINION_IDEA.short))
    sentiments.append(f)

    return sentiments


def _get_platforms(request, product, platform, q):
    """Get platforms."""
    platforms = []
    url = request.get_full_path()

    f = Filter(urlparams(url, p=None), _('All'), _('All Platforms'),
               (not platform or platform == 'all'))
    platforms.append(f)

    platforms_from_es = q.get_facet('platform')
    for p in platforms_from_es.keys():
        if p not in PLATFORMS:
            continue
        f = Filter(urlparams(url, p=p), p, PLATFORMS[p].pretty,
                   (platform == p))
        platforms.append(f)

    return platforms


def _get_products(request, product):
    """Get product filters."""
    products = []
    url = request.get_full_path()

    for prod in PRODUCT_USAGE:
        f = Filter(urlparams(url, a=prod.short), prod.pretty, prod.pretty,
                   (product == prod.short))
        products.append(f)

    return products


def _get_versions(request, version, q):
    """Get version filters."""
    versions = []
    url = request.get_full_path()
    for v in version_list(q.get_facet('version'), reverse=False):
        f = Filter(urlparams(url, version=v), v, v, (version == v))
        versions.append(f)

    return versions


def _process_filters(filters):
    qfilters = []
    for field, value in filters.iteritems():
        qfilters.append(dict(term={field: value}))

    if len(qfilters) > 1:
        return {'and': qfilters}
    else:
        return qfilters[0]


class Theme(object):
    def __init__(self, slug, text, type, product, platform, version):
        self.opinions = []
        self.slug = slug
        self.text = text
        self.type = type
        self.product = input.PRODUCT_IDS.get(product) or input.FIREFOX
        self.platform = platform
        self.version = version
        self.total = 0

    def get_absolute_url(self):
        return reverse('theme', args=[self.type, self.product.short,
                                      self.version, self.platform, self.slug])

    @classmethod
    def from_results(cls, results):
        hits = results['hits']['hits']
        z = [h['_source']['items'][:6] for h in hits
             if 'items' in h['_source']]
        items = sum(z, [])

        opinions = dict(((o.id, o) for o in
                         Opinion.objects.filter(pk__in=items)))

        themes = []
        for hit in hits:
            theme = cls.parse_hit(hit, opinions)
            themes.append(theme)

        return themes

    @classmethod
    def parse_hit(cls, hit, opinions=None):
        s = hit['_source']
        theme = Theme(slug=s['slug'], text=s['text'], type=s['type'],
                      product=s['product'], platform=s['platform'],
                      version=s['version'])
        if opinions:
            theme.opinions = [opinions[k] for k in s['items'][:6]
                              if k in opinions]
        else:
            theme.opinions = Opinion.objects.filter(pk__in=s['items'])

        theme.total = s['size']
        return theme


es_disabled_msg = _lazy('Firefox Input does not support themes yet.')
es_broken = _lazy('Firefox Input had trouble finding themes at the moment.  '
                  'Please try again later.')


@cache_page(use_get=True)
@es_required_or_50x(es_disabled_msg, es_broken)
def index(request):
    """List the themes clusters."""
    # query parameters
    product = request.GET.get('a', FIREFOX.short)
    product_full = PRODUCTS.get(product) or FIREFOX
    sentiment = request.GET.get('s')
    platform = request.GET.get('p', 'all')
    version = request.GET.get('version', product_full.default_version)
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1
    q = (S(product=product_full.id, type=settings.ES_TYPE_THEME,
           result_transform=Theme.from_results)
         .filter(version=version, platform=platform)
         .facet('version').facet('platform').facet('type')
         .order_by('-size'))
    if sentiment:
        q.filter(type=sentiment)
    pp = settings.SEARCH_PERPAGE
    pager = Paginator(q, pp)

    products = _get_products(request, product)
    platforms = _get_platforms(request, product, platform, q)
    sentiments = _get_sentiments(request, sentiment)
    versions = _get_versions(request, version, q)

    args = dict(sentiments=sentiments, platforms=platforms, products=products,
                versions=versions)

    try:
        args['page'] = pager.page(page)
    except (EmptyPage, InvalidPage):
        args['page'] = pager.page(pager.num_pages)

    args['themes'] = args['page'].object_list
    return jingo.render(request, 'themes/index.html', args)


@cache_page(use_get=True)
def theme(request, sentiment, product, version, platform, slug):
    es = get_es()
    id = '-'.join([product, version, platform, sentiment, slug])

    try:
        theme = Theme.parse_hit(es.get(
            settings.ES_INDEX, settings.ES_TYPE_THEME, iri_to_uri(id)))

    except ElasticSearchException:
        raise http.Http404

    pager = Paginator(theme.opinions, settings.SEARCH_PERPAGE)
    try:
        page = pager.page(request.GET.get('page', 1))
    except (EmptyPage, InvalidPage):
        page = pager.page(pager.num_pages)

    return jingo.render(request,
                        'themes/theme.html',
                        {"theme": theme,
                         "opinions": page.object_list,
                         "page": page,
                         "exit_url": reverse("themes")})
