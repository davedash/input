import logging

from django.conf import settings
from django.http import Http404

import cronjobs
from celery.messaging import establish_connection
from celeryutils import task, chunked
from elasticutils import get_es
from slugify import slugify

import input
from feedback.models import Opinion
from grouperfish import GF
from themes.utils import cluster_key

log = logging.getLogger('reporter')


@cronjobs.register
def grouperfish_index_all():
    """This shouldn't be run that often."""
    ids = (Opinion.objects
                  .filter(_type__in=[o.id for o in input.OPINION_USAGE])
                  .order_by('product', 'version', 'platform', '_type')
                  .values_list('id', flat=True))
    with establish_connection() as c:
        for chunk in chunked(ids, 1000):
            _grouperfish_index.apply_async(args=[chunk], connection=c)


@task
def _grouperfish_index(items, **kw):
    if not settings.GF_HOST:
        log.debug('GrouperFish not configured.')
        return
    log.info('[%d@%s] Sending to GrouperFish' %
             (len(items), _grouperfish_index.rate_limit))

    with GF as c:
        for opinion in Opinion.objects.filter(pk__in=items):
            opinion.post_to_grouperfish(connection=c)


@cronjobs.register
def update_clusters():
    """
    Takes things from GrouperFish and puts them in ElasticSearch:

    Verify via:

    curl  -XGET http://127.0.0.1:9202/input/themes/_search\?pretty\=true
    -d '{
            "query": { "match_all": {} }
        }'
    """
    gf = GF(settings.GF_HOST, settings.GF_NAMESPACE)
    es = get_es()

    for product in input.PRODUCT_USAGE:
        for version in set((input.LATEST_BETAS[product],
                            input.LATEST_RELEASE[product],
                            product.default_version)):
            for type in input.OPINION_USAGE:
                for platform in (['all'] +
                                 [p.short for p in input.PLATFORM_USAGE
                                  if product in p.prods]):
                    key = cluster_key(product, version, platform, type)
                    log.debug(key)
                    try:
                        clusters = gf.fetch(key)
                    except Http404:
                        continue
                    for text, items in clusters.iteritems():
                        slug = slugify(text)
                        data = dict(
                                slug=slug,
                                text=text,
                                platform=platform,
                                product=product.id,
                                type=type.short,
                                version=version,
                                items=[int(x) for x in items],
                                size=len(items)
                                )
                        es.index(data, settings.ES_INDEX, 'theme',
                                 id='%s-%s' % (key, slug), bulk=True)
    es.refresh()
