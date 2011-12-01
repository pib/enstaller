import sys
import json
import urlparse
import urllib2
from base import AbstractRepo


class RemoteHTTPRepo(AbstractRepo):

    def __init__(self, url):
        self.root_url = url

    def connect(self, userpass=None):
        self.userpass = userpass  # tuple(username, password)

        fp = self.get('index.json')
        if fp is None:
            raise Exception("Could not connect")
        self._index = json.load(fp)
        fp.close()

    def info(self):
        return {'summary': 'simple remote HTTP repository'}

    def get(self, key, default=None):
        url = self.root_url + key
        print url
        scheme, netloc, path, params, query, frag = urlparse.urlparse(url)
        auth, host = urllib2.splituser(netloc)
        if auth:
            auth = urllib2.unquote(auth).encode('base64').strip()
        elif self.userpass:
            auth = ('%s:%s' % self.userpass).encode('base64').strip()

        if auth:
            new_url = urlparse.urlunparse((scheme, host, path,
                                           params, query, frag))
            request = urllib2.Request(new_url)
            request.add_unredirected_header("Authorization", "Basic " + auth)
        else:
            request = urllib2.Request(url)
        request.add_header('User-Agent', 'enstaller')
        try:
            return urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            sys.stderr.write("%s: %r\n" % (e, url))
            return default

    def set(self, key, value, buffer_size=1048576):
        pass

    def delete(self, key):
        pass

    def get_metadata(self, key, default=None):
        try:
            return self._index[key]
        except KeyError:
            return default

    def exists(self, key):
        pass

    def query(self, **kwargs):
        res = {}
        for key in self.query_keys(**kwargs):
            res[key] = self._index[key]
        return res

    def query_keys(self, **kwargs):
        for key, info in self._index.iteritems():
            if all(info.get(k) in (v, None)
                   for k, v in kwargs.iteritems()):
                yield key


if __name__ == '__main__':
    url='https://www.enthought.com/repo/epd/eggs/RedHat/RH5_amd64/'
    r = RemoteHTTPRepo(url)
    r.open(('EPDUser', 'Epd789'))
    print r.query(name='bsdiff4')
