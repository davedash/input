from django.conf import settings

import commonware.log
import cronjobs
import pyes.exceptions as pyes
from celery.messaging import establish_connection
from celeryutils import chunked
from elasticutils import get_es

import input
from feedback.models import Opinion
from search import tasks

log = commonware.log.getLogger('i.cron')


@cronjobs.register
def index_all():
    """
    This reindexes all the Opinions in usage.  This is not intended to be run
    other than to initially seed Elastic Search.
    """
    ids = (Opinion.objects
           .filter(_type__in=[i.id for i in input.OPINION_USAGE])
           .values_list('id', flat=True))
    with establish_connection() as conn:
        for chunk in chunked(ids, 1000):
            tasks.add_to_index.apply_async(args=[chunk], connection=conn)


@cronjobs.register
def setup_mapping():
    m = dict(
            product=dict(type='long', ),
            )
    es = get_es()
    try:
        es.create_index_if_missing(settings.ES_INDEX)
        es.put_mapping('opinion', {'properties': m}, settings.ES_INDEX)
    except pyes.ElasticSearchException as e:
        log.debug(e)
