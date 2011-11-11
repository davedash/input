import datetime
import random
import logging

from django.conf import settings
from django.db import transaction, models

import cronjobs
from product_details.version_compare import Version

import input
from feedback.models import Opinion, VersionCount, extract_terms


DEFAULT_NUM_OPINIONS = 100
TYPES = list(input.OPINION_TYPES_USAGE)
URLS = ['http://google.com', 'http://mozilla.com', 'http://bit.ly', '', '']
text = """
    To Sherlock Holmes she is always the woman. I have seldom heard him mention
    her under any other name. In his eyes she eclipses and predominates the
    whole of her sex. It was not that he felt any emotion akin to love for
    Irene Adler. All emotions, and that one particularly, were abhorrent to his
    cold, precise but admirably balanced mind. He was, I take it, the most
    perfect reasoning and observing machine that the world has seen, but as a
    lover he would have placed himself in a false position. He never spoke of
    the softer passions, save with a gibe and a sneer. They were admirable
    things for the observer-excellent for drawing the veil from men's motives
    and actions. But for the trained reasoner to admit such intrusions into his
    own delicate and finely adjusted temperament was to introduce a distracting
    factor which might throw a doubt upon all his mental results. Grit in a
    sensitive instrument, or a crack in one of his own high-power lenses, would
    not be more disturbing than a strong emotion in a nature such as his. And
    yet there was but one woman to him, and that woman was the late Irene
    Adler, of dubious and questionable memory.
    """

sample = lambda: ' '.join(random.sample(text.split(), 15))
UA_STRINGS = {'mobile': ['Mozilla/5.0 (Android; Linux armv71; rv:2.0b6pre)'
                         ' Gecko/20100924 Namoroka/4.0b7pre Fennec/2.0b1pre'],
              'desktop': ['Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; '
                          'fr-FR; rv:2.0b1) Gecko/20100628 Firefox/%s' % (
                              input.FIREFOX.default_version),

                          'Mozilla/5.0 (Windows; U; Windows NT 5.1; '
                          'en-US; rv:1.9.2.4) Gecko/20100611 Firefox/%s '
                          '(.NET CLR 3.5.30729)' % (
                              input.FIREFOX.default_version),

                          'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; '
                          'fr-FR; rv:2.0b1) Gecko/20100628 Firefox/%s' % (
                              input.FIREFOX.default_version),
                          ]}
DEVICES = dict(Samsung='Epic Vibrant Transform'.split(),
               HTC='Evo Hero'.split(),
               Motorola='DroidX Droid2'.split())
logger = logging.getLogger(__name__)


@cronjobs.register
@transaction.commit_on_success
def populate(num_opinions=None, product='mobile', type=None, locale=None):
    models.signals.post_save.disconnect(extract_terms, sender=Opinion,
                                        dispatch_uid='extract_terms')

    if not num_opinions:
        num_opinions = getattr(settings, 'NUM_FAKE_OPINIONS',
                               DEFAULT_NUM_OPINIONS)
    else:
        num_opinions = int(num_opinions)

    if hasattr(type, 'id'):  # Take "3" as well as OPINION_IDEA
        type = type.id

    for i in xrange(num_opinions):
        if not type:
            type = random.choice(TYPES).id
        o = Opinion(_type=type,
                    url=random.choice(URLS),
                    locale=locale or random.choice(settings.PROD_LANGUAGES),
                    user_agent=random.choice(UA_STRINGS[product]))

        o.description = sample()

        if product == 'mobile':
            manufacturer = random.choice(DEVICES.keys())
            o.manufacturer = manufacturer
            o.device = random.choice(DEVICES[manufacturer])

        o.save()

        o.created = datetime.datetime.now() - datetime.timedelta(
                seconds=random.randint(0, 30 * 24 * 3600))
        o.save()

    models.signals.post_save.connect(extract_terms, sender=Opinion,
                                     dispatch_uid='extract_terms')


@cronjobs.register
def version_counter():
    """Cron to activate and deactivate product versions."""
    thirtydaysago = datetime.datetime.now() - datetime.timedelta(30)
    versions = (Opinion.objects.filter(created__gte=(thirtydaysago))
                       .values('product', 'version')
                       .annotate(count=models.Count('id')))
    logger.debug("Found %d versions" % (len(versions)))
    for version in versions:
        vc, created = VersionCount.objects.get_or_create(
                product=version['product'], version=version['version'],
                defaults={'num_opinions': version['count']})
        if not created:
            vc.num_opinions = version['count']
        if vc.product == input.FIREFOX.id:
            vc.active = (vc.num_opinions >= settings.DASHBOARD_THRESHOLD)
        else:
            vc.active = (
                vc.num_opinions >= settings.DASHBOARD_THRESHOLD_MOBILE)
        vc.save()
