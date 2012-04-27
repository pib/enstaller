import json
import urlparse
import urllib2
from collections import defaultdict

from base import AbstractStore


class IndexedStore(AbstractStore):

    def connect(self, userpass=None):
        self.userpass = userpass  # tuple(username, password)

        self._index = self.get_index()

        #for k, v in self._index.iteritems():
        #    print k, v

        for info in self._index.itervalues():
            info['store_location'] = self.info().get('root')
            info.setdefault('type', 'egg')
            info.setdefault('python', '2.7')
            info.setdefault('packages', [])

        # maps names to keys
        self._groups = defaultdict(list)
        for key, info in self._index.iteritems():
            self._groups[info['name']].append(key)

    def get_index(self):
        fp = self.get_data('index.json')
        if fp is None:
            raise Exception("could not connect")
        return json.load(fp)

    def _location(self, key):
        rt = self.root.rstrip('/') + '/'
        if key.endswith('.zdiff'):
            return rt + 'patches/' + key
        return rt + key

    def get(self, key):
        return self.get_data(key), self.get_metadata(key)

    def get_metadata(self, key):
        return self._index[key]

    def exists(self, key):
        return key in self._index

    def query(self, **kwargs):
        for key in self.query_keys(**kwargs):
            yield key, self._index[key]

    def query_keys(self, **kwargs):
        name = kwargs.get('name')
        if name is None:
            for key, info in self._index.iteritems():
                if all(info.get(k) == v for k, v in kwargs.iteritems()):
                    yield key
        else:
            del kwargs['name']
            for key in self._groups[name]:
                info = self._index[key]
                if all(info.get(k) == v for k, v in kwargs.iteritems()):
                    yield key


class LocalIndexedStore(IndexedStore):

    def __init__(self, root_dir):
        self.root = root_dir

    def info(self):
        return dict(root=self.root)

    def get_data(self, key):
        try:
            return open(self._location(key), 'rb')
        except IOError as e:
            raise KeyError(str(e))


class RemoteHTTPIndexedStore(IndexedStore):

    def __init__(self, url):
        self.root = url

    def info(self):
        return dict(root=self.root)

    def get_data(self, key):
        url = self._location(key)
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
            raise KeyError("%s: %s" % (e, url))
        except urllib2.URLError as e:
            raise Exception("Could not connect to %s" %(host,))
