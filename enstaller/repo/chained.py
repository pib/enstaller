from base import AbstractRepo


class ChainedRepo(AbstractRepo):

    def __init__(self, repos):
        self.repos = repos

    def connect(self, auth=None):
        for repo in self.repos:
            repo.connect(auth)

    def get(self, key, default=None):
        for repo in self.repos:
            if repo.exists(key):
                return repo.get(key)
        return default

    def get_metadata(self, key, default=None):
        for repo in self.repos:
            if repo.exists(key):
                return repo.get_metadata(key)
        return default

    def exists(self, key):
        for repo in self.repos:
            if repo.exists(key):
                return True
        return False

    def query(self, **kwargs):
        index = {}
        for repo in reversed(self.repos):
            index.update(repo.query(**kwargs))
        for key, meta in index.iteritems():
            yield key, meta


if __name__ == '__main__':
    from indexed import LocalIndexedRepo

    r = ChainedRepo([LocalIndexedRepo('/Users/ischnell/repo'),
                     LocalIndexedRepo('/Users/ischnell/repo2'),
                     ])
    r.connect()
    for key in r.query_keys():#name='Cython'):
        print key
