import os
import sys
import hashlib
import zipfile
from collections import defaultdict
from os.path import basename, isfile, isdir, join

from egginst.utils import human_bytes

from enstaller.store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore

from enstaller.utils import comparable_version, md5_file
import metadata
import dist_naming
from requirement import Req, add_Reqs_to_spec


def stream_to_file(fi, path, info={}):
    """
    Read data from the filehandle and write a the file.
    Optionally check the MD5.
    """
    size = info['size']
    md5 = info.get('md5')

    print "Fetching: %s (%s)" % (basename(path), human_bytes(size))

    n = 0
    h = hashlib.new('md5')
    with open(path + '.part', 'wb') as fo:
        while True:
            chunk = fi.read(16384)
            if not chunk:
                break
            fo.write(chunk)
            if md5:
                h.update(chunk)
            n += len(chunk)
    fi.close()

    if md5 and h.hexdigest() != md5:
        raise Exception("Error: received data MD5 sums mismatch")
    os.rename(path + '.part', path)


class Chain(object):

    def __init__(self, repos=[], verbose=False):
        self.verbose = verbose

        # maps distributions to specs
        self.index = {}

        # maps cnames to the list of distributions (in repository order)
        self.groups = defaultdict(list)

        # maps the url of a repo to repository objects
        self.repo_objs = {}

        # Chain of repositories, either local or remote
        self.repos = []
        for repo in repos:
            # These are file:// (optionally indexed) or http:// (indexed)
            self.add_repo(repo)

        if self.verbose:
            self.print_repos()


    def print_repos(self):
        print 'Repositories:'
        for r in self.repos:
            print '  %r' % r
        print


    def connect(self, repo):
        if repo in self.repo_objs:
            return self.repo_objs[repo]

        if repo.startswith('file://'):
            r = LocalIndexedStore(repo[7:])
            r.connect()

        elif repo.startswith(('http://', 'https://')):
            r = RemoteHTTPIndexedStore(repo)
            if repo.startswith('https://'):
                r.connect(userpass=('EPDUser', 'Epd789'))
            else:
                r.connect()

        self.repo_objs[repo] = r
        return r


    def add_repo(self, repo, index_fn=None):
        """
        Add a repo to the chain, i.e. read the index file of the url,
        parse it and update the index.
        """
        if self.verbose:
            print "Adding repository:"
            print "   URL:", repo
        repo = dist_naming.cleanup_reponame(repo)
        self.repos.append(repo)

        if index_fn: # for running the tests locally
            assert repo.startswith('file://')
            index_data = open(repo[7:] + index_fn).read()
            new_index = metadata.parse_depend_index(index_data)

        else:
            new_index = dict(self.connect(repo).query(type='egg'))

        for spec in new_index.itervalues():
            add_Reqs_to_spec(spec)

        for distname, spec in new_index.iteritems():
            dist = repo + distname
            self.index[dist] = spec
            self.groups[spec['cname']].append(dist)


    def get_version_build(self, dist):
        """
        Returns a tuple(version, build) for a distribution, version is a
        RationalVersion object (see verlib).  This method is used below
        for determining the distribution with the largest version and build
        number.
        """
        return dist_naming.comparable_spec(self.index[dist])


    def iter_dists(self, req):
        """
        iterate over all distributions matching the requirement (in
        repository order)
        """
        assert req.strictness >= 1
        for dist in self.groups[req.name]:
            if req.matches(self.index[dist]):
                yield dist


    def get_repo(self, req):
        """
        return the first repository in which the requirement matches at least
        one distribution
        """
        for dist in self.iter_dists(req):
            return dist_naming.repo_dist(dist)
        return None


    def get_dist(self, req):
        """
        return the distributions with the largest version and build number
        from the first repository which contains any matches
        """
        repo = self.get_repo(req)
        if repo is None:
            return None

        matches = []
        for dist in self.iter_dists(req):
            if dist_naming.repo_dist(dist) == repo:
                matches.append(dist)
        return max(matches, key=self.get_version_build)


    def reqs_dist(self, dist):
        """
        return the set of requirement objects listed by the given
        distribution
        """
        return self.index[dist]['Reqs']


    def cname_dist(self, dist):
        """
        return the canonical project name for a given distribution
        """
        return self.index[dist]['cname']


    def are_complete(self, dists):
        """
        return True if the distributions 'dists' are complete, i.e. the for
        each distribution all dependencies (by name only) are also included
        in the 'dists'
        """
        cnames = set(self.cname_dist(d) for d in dists)
        for dist in dists:
            for r in self.reqs_dist(dist):
                if r.name not in cnames:
                    return False
        return True


    def determine_install_order(self, dists):
        """
        given the distributions 'dists' (which are already complete, i.e.
        the for each distribution all dependencies are also included in
        the 'dists'), return a list of the same distribution in the correct
        install order
        """
        dists = list(dists)
        assert self.are_complete(dists)

        # make sure each project name is listed only once
        assert len(dists) == len(set(self.cname_dist(d) for d in dists))

        # the distributions corresponding to the requirements must be sorted
        # because the output of this function is otherwise not deterministic
        dists.sort(key=self.cname_dist)

        # maps dist -> set of required (project) names
        rns = {}
        for dist in dists:
            rns[dist] = set(r.name for r in self.reqs_dist(dist))

        # as long as we have things missing, simply look for things which
        # can be added, i.e. all the requirements have been added already
        result = []
        names_inst = set()
        while len(result) < len(dists):
            n = len(result)
            for dist in dists:
                if dist in result:
                    continue
                # see if all required packages were added already
                if all(bool(name in names_inst) for name in rns[dist]):
                    result.append(dist)
                    names_inst.add(self.index[dist]['cname'])
                    assert len(names_inst) == len(result)

            if len(result) == n:
                # nothing was added
                raise Exception("Loop in dependency graph\n%r" %
                                [dist_naming.filename_dist(d) for d in dists])
        return result


    def _sequence_flat(self, root):
        dists = [root]
        for r in self.reqs_dist(root):
            d = self.get_dist(r)
            if d is None:
                sys.exit('Error: could not resolve %r' % r)
            dists.append(d)

        can_order = self.are_complete(dists)
        if self.verbose:
            print "Can determine install order:", can_order
        if can_order:
            dists = self.determine_install_order(dists)
        return dists


    def _sequence_recur(self, root):
        reqs_shallow = {}
        for r in self.reqs_dist(root):
            reqs_shallow[r.name] = r
        reqs_deep = defaultdict(set)

        def add_dependents(dist):
            for r in self.reqs_dist(dist):
                reqs_deep[r.name].add(r)
                if (r.name in reqs_shallow  and
                        r.strictness < reqs_shallow[r.name].strictness):
                    continue
                d = self.get_dist(r)
                if d is None:
                    sys.exit('Error: could not resolve %r required by %r' %
                             (r, dist))
                dists.add(d)
                add_dependents(d)

        dists = set([root])
        add_dependents(root)

        cnames = set(self.cname_dist(d) for d in dists)
        if len(dists) != len(cnames):
            for cname in cnames:
                ds = [d for d in dists if self.cname_dist(d) == cname]
                assert len(ds) != 0
                if len(ds) == 1:
                    continue
                if self.verbose:
                    print 'multiple: %s' % cname
                    for d in ds:
                        print '    %s' % d
                r = max(reqs_deep[cname], key=lambda r: r.strictness)
                assert r.name == cname
                # remove the dists with name 'cname'
                dists = [d for d in dists if self.cname_dist(d) != cname]
                # add the one
                dists.append(self.get_dist(r))

        return self.determine_install_order(dists)


    def install_sequence(self, req, mode='recur'):
        """
        Return the list of distributions which need to be installed.
        The returned list is given in dependency order.
        The 'mode' may be:

        'root':  only the distribution for the requirement itself is
                 contained in the result (but not any dependencies)

        'flat':  dependencies are handled only one level deep

        'recur': dependencies are handled recursively (default)
        """
        if self.verbose:
            print "Determining install sequence for %r" % req
        root = self.get_dist(req)
        if root is None:
            return None

        if mode == 'root':
            return [root]

        if mode == 'flat':
            return self._sequence_flat(root)

        if mode == 'recur':
            return self._sequence_recur(root)

        raise Exception('did not expect: mode = %r' % mode)


    def list_versions(self, name):
        """
        given the name of a package, retruns a sorted list of versions for
        package `name` found in any repo.
        """
        versions = set()

        req = Req(name)
        for dist in self.groups[req.name]:
            spec = self.index[dist]
            if req.matches(spec):
                versions.add(spec['version'])

        try:
            return sorted(versions, key=comparable_version)
        except TypeError:
            return list(versions)


    def fetch_dist(self, dist, fetch_dir, force=False, dry_run=False):
        """
        Get a distribution, i.e. copy or download the distribution into
        fetch_dir.

        force:
            force download or copy if MD5 mismatches
        """
        info = self.index[dist]
        repo, fn = dist_naming.split_dist(dist)
        path = join(fetch_dir, fn)
        # if force is used, make sure the md5 is the expected, otherwise
        # only see if the file exists
        if isfile(path) and (not force or md5_file(path) == info.get('md5')):
            if self.verbose:
                print "Not forcing refetch, %r already matches MD5" % path
            return

        if dry_run:
            return

        if self.verbose:
            print "Fetching: %r" % dist
            print "      to: %r" % path

        stream_to_file(self.repo_objs[repo].get_data(fn), path, info)


    def index_file(self, filename, repo):
        """
        Add an unindexed distribution, which must already exist in a local
        repository to the index (in memory).  Note that the index file on
        disk remains unchanged.
        """
        assert filename == basename(filename), filename
        dist = repo + filename
        if self.verbose:
            print "Adding %r to index" % dist

        arcname = 'EGG-INFO/spec/depend'
        z = zipfile.ZipFile(join(dist_naming.dirname_repo(repo), filename))
        if arcname not in z.namelist():
            z.close()
            raise Exception("zipfile %r has no arcname=%r" %
                            (filename, arcname))

        spec = metadata.parse_data(z.read(arcname))
        z.close()
        add_Reqs_to_spec(spec)
        self.index[dist] = spec
        self.groups[spec['cname']].append(dist)


    def index_all_files(self, repo):
        """
        Add all distributions to the index, see index_file() above.
        Note that no index file is written to disk.
        """
        dir_path = dist_naming.dirname_repo(repo)
        assert isdir(dir_path), dir_path
        for fn in os.listdir(dir_path):
            if not fn.endswith('.egg'):
                continue
            if not dist_naming.is_valid_eggname(fn):
                print "WARNING: ignoring invalid egg name:", join(dir_path, fn)
                continue
            self.index_file(fn, repo)


def main():
    from optparse import OptionParser

    p = OptionParser(usage="usage: %prog [options] REPO [EGG ...]",
                     description="simple interface to fetch eggs")
    p.add_option("--dst",
                 action="store",
                 help="destination directory",
                 default=os.getcwd(),
                 metavar='PATH')
    p.add_option('-v', "--verbose", action="store_true")

    opts, args = p.parse_args()

    if len(args) < 1:
        p.error('at least one argument expected, try -h')

    repo = args[0]
    c = Chain([repo], opts.verbose)
    for fn in args[1:]:
        if not dist_naming.is_valid_eggname(fn):
            sys.exit('Error: invalid egg name: %r' % fn)
        c.fetch_dist(repo + fn, opts.dst)


if __name__ == '__main__':
    sys.exit(main())
