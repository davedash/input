from django.conf import settings
from django.contrib.sites.models import Site

from input.urlresolvers import reverse
from input.tests import InputTestCase, enforce_ua


class RedirectTests(InputTestCase):
    @enforce_ua
    def test_redirects(self):
        redirect = lambda x: '/en-US/%s' % x
        redirs = {
                '/feedback': '/en-US/feedback',
                '/thanks': '/en-US/thanks',
                '/sites': redirect('sites'),
                '/en-US/beta/sites': redirect('sites'),
                }
        for link, redir in redirs.iteritems():
            self.assertRedirects(self.fxclient.get(link, follow=True), redir,
                                 301)

    def test_mobile(self):
        """
        Verify mobile redirects work using a mobile browser.

        Verify that accessing the root of the site with a mobile User-Agent
        causes a redirect (this is how we route mobile users to m.input).
        Makes sure redirects only happen with a desktop browser too.
        """
        # Make sure the mobile site is defined in the test DB
        Site.objects.create(pk=settings.MOBILE_SITE_ID,
                            domain='m.input.mozillatest.com',
                            name='m.input.mozillatest.com')

        r = self.fxclient.get(reverse('search'))
        assert r.status_code in (200, 500)  # Sphinx will be down...
        r = self.mclient.get(reverse('search'))
        assert r.status_code == 302

    def test_search(self):
        r = self.fxclient.get('/', follow=True)
        assert r.status_code != 404
