import sys
from collections import defaultdict

from indexed_repo.dist_naming import comparable_spec
from indexed_repo.requirement import Req, add_Reqs_to_spec


class Resolve(object):

    def __init__(self, repo, verbose=False):
        self.repo = repo
        self.verbose = verbose

    def get_egg(self, req):
        """
        return the egg with the largest version and build number
        """
        assert req.strictness >= 1
        d = dict(self.repo.query(name=req.name))
        if not d:
            return None
        matches = []
        for key, spec in d.iteritems():
            add_Reqs_to_spec(spec)
            if req.matches(spec):
                matches.append(key)
        if not matches:
            return None
        return max(matches, key=lambda k: comparable_spec(d[k]))

    def reqs_egg(self, egg):
        """
        return the set of requirement objects listed by the given egg
        """
        return set(Req(s) for s in self.repo.get_metadata(egg)['packages'])

    def cname_egg(self, egg):
        """
        return the project name for a given egg (from it's meta data)
        """
        return self.repo.get_metadata(egg)['name']

    def are_complete(self, eggs):
        """
        return True if the 'eggs' are complete, i.e. the for each egg all
        dependencies (by name only) are also included in 'eggs'
        """
        cnames = set(self.cname_egg(d) for d in eggs)
        for egg in eggs:
            for r in self.reqs_egg(egg):
                if r.name not in cnames:
                    return False
        return True

    def determine_install_order(self, eggs):
        """
        given the 'eggs' (which are already complete, i.e. the for each
        egg all dependencies are also included in 'eggs'), return a list
        of the same eggs in the correct install order
        """
        eggs = list(eggs)
        assert self.are_complete(eggs)

        # make sure each project name is listed only once
        assert len(eggs) == len(set(self.cname_egg(d) for d in eggs))

        # the eggs corresponding to the requirements must be sorted
        # because the output of this function is otherwise not deterministic
        eggs.sort(key=self.cname_egg)

        # maps egg -> set of required (project) names
        rns = {}
        for egg in eggs:
            rns[egg] = set(r.name for r in self.reqs_egg(egg))

        # as long as we have things missing, simply look for things which
        # can be added, i.e. all the requirements have been added already
        result = []
        names_inst = set()
        while len(result) < len(eggs):
            n = len(result)
            for egg in eggs:
                if egg in result:
                    continue
                # see if all required packages were added already
                if all(bool(name in names_inst) for name in rns[egg]):
                    result.append(egg)
                    names_inst.add(self.cname_egg(egg))
                    assert len(names_inst) == len(result)

            if len(result) == n:
                # nothing was added
                raise Exception("Loop in dependency graph\n%r" % eggs)
        return result

    def _sequence_flat(self, root):
        eggs = [root]
        for r in self.reqs_egg(root):
            d = self.get_egg(r)
            if d is None:
                sys.exit('Error: could not resolve %r' % r)
            eggs.append(d)

        can_order = self.are_complete(eggs)
        if self.verbose:
            print "Can determine install order:", can_order
        if can_order:
            eggs = self.determine_install_order(eggs)
        return eggs

    def _sequence_recur(self, root):
        reqs_shallow = {}
        for r in self.reqs_egg(root):
            reqs_shallow[r.name] = r
        reqs_deep = defaultdict(set)

        def add_dependents(egg):
            for r in self.reqs_egg(egg):
                reqs_deep[r.name].add(r)
                if (r.name in reqs_shallow  and
                        r.strictness < reqs_shallow[r.name].strictness):
                    continue
                d = self.get_egg(r)
                if d is None:
                    sys.exit('Error: could not resolve %r required by %r' %
                             (r, egg))
                eggs.add(d)
                add_dependents(d)

        eggs = set([root])
        add_dependents(root)

        cnames = set(self.cname_egg(d) for d in eggs)
        if len(eggs) != len(cnames):
            for cname in cnames:
                ds = [d for d in eggs if self.cname_egg(d) == cname]
                assert len(ds) != 0
                if len(ds) == 1:
                    continue
                if self.verbose:
                    print 'multiple: %s' % cname
                    for d in ds:
                        print '    %s' % d
                r = max(reqs_deep[cname], key=lambda r: r.strictness)
                assert r.name == cname
                # remove the eggs with name 'cname'
                eggs = [d for d in eggs if self.cname_egg(d) != cname]
                # add the one
                eggs.append(self.get_egg(r))

        return self.determine_install_order(eggs)

    def install_sequence(self, req, mode='recur'):
        """
        Return the list of eggs which need to be installed.
        The returned list is given in dependency order.
        The 'mode' may be:

        'root':  only the egg for the requirement itself is
                 contained in the result (but not any dependencies)

        'flat':  dependencies are handled only one level deep

        'recur': dependencies are handled recursively (default)
        """
        if self.verbose:
            print "Determining install sequence for %r" % req
        root = self.get_egg(req)
        if root is None:
            return None

        if mode == 'root':
            return [root]

        if mode == 'flat':
            return self._sequence_flat(root)

        if mode == 'recur':
            return self._sequence_recur(root)

        raise Exception('did not expect: mode = %r' % mode)


if __name__ == '__main__':
    from repo.indexed import LocalIndexedRepo
    from repo.chained import ChainedRepo

    r = ChainedRepo([LocalIndexedRepo('/Users/ischnell/repo'),
                     LocalIndexedRepo('/Users/ischnell/repo2'),
                     ])
    r.connect()
    res = Resolve(r)
    print res.get_egg(Req('pyside'))
    print list(r.query_keys(name='nose'))
    print res.install_sequence(Req('pyside'))
