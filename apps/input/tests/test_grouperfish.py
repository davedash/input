from StringIO import StringIO

from mock import patch
from nose.tools import eq_

from grouperfish import GF


class FakeUrlopen(StringIO):
    def getcode(self):
        return 200

@patch('urllib.urlopen')
def test_gf(urlopen):
    gf = GF('host', 'space')

    urlopen.return_value = FakeUrlopen('/awesome')
    eq_(gf.index('woo'), 'host/awesome')

    urlopen.return_value = FakeUrlopen('{"hi": "there"}')
    eq_(gf.fetch('ww'), {'hi': 'there'})

