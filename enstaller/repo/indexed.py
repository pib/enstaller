import sys
import json
import urlparse
import urllib2
from os.path import join
from base import AbstractRepo


class IndexedRepo(AbstractRepo):

    def connect(self, userpass=None):
        self.userpass = userpass  # tuple(username, password)

        fp = self.get('index.json')
        if fp is None:
            raise Exception("Could not connect")
        self._index = json.load(fp)
        fp.close()

    def get_metadata(self, key, default=None):
        try:
            return self._index[key]
        except KeyError:
            return default

    def exists(self, key):
        return key in self._index

    def query(self, **kwargs):
        for key in self.query_keys(**kwargs):
            yield key, self._index[key]

    def query_keys(self, **kwargs):
        for key, info in self._index.iteritems():
            if all(info.get(k) in (v, None) for k, v in kwargs.iteritems()):
                yield key


class LocalIndexedRepo(IndexedRepo):

    def __init__(self, root_dir):
        self.root_dir = root_dir

    def get(self, key, default=None):
        try:
            return open(join(self.root_dir, key), 'rb')
        except IOError as e:
            sys.stderr.write("%s\n" % e)
            return default


class RemoteHTTPIndexedRepo(IndexedRepo):

    def __init__(self, url):
        self.root_url = url

    def get(self, key, default=None):
        url = self.root_url + key
        scheme, netloc, path, params, query, frag = urlparse.urlparse(url)
        auth, host = urllib2.splituser(netloc)
        if auth:
            auth = urllib2.unquote(auth) 
        elif self.userpass:
            auth = ('%s:%s' % self.userpass)

        if auth:
            new_url = urlparse.urlunparse((scheme, host, path,
                                           params, query, frag))
            request = urllib2.Request(new_url)
            request.add_unredirected_header("Authorization",
                                "Basic " + auth.encode('base64').strip())
        else:
            request = urllib2.Request(url)
        request.add_header('User-Agent', 'enstaller')
        try:
            return urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            sys.stderr.write("%s: %r\n" % (e, url))
            return default
