# Author: Ilan Schnell <ischnell@enthought.com>
"""\
enstaller is a managing tool for egginst-based installs, and the CLI is
called enpkg which calls out to egginst to do the actual install.
enpkg can access distributions from local and HTTP repositories.
"""
import os
import re
import sys
import string
import subprocess
import textwrap
from argparse import ArgumentParser
from os.path import isdir, isfile, join

import egginst
from egginst.utils import bin_dir_name, rel_site_packages, pprint_fn_action, \
                   console_file_progress

from enstaller import __version__
import config
from history import History
from proxy.api import setup_proxy
from utils import (canonical, cname_fn, get_info, comparable_version,
                   shorten_repo, get_installed_info, get_available)
from indexed_repo import (Chain, Req, add_Reqs_to_spec, filename_as_req,
                          spec_as_req, parse_data, dist_naming)


class DistributionNotFound(Exception):
    pass


class DistributionVersionMismatch(Exception):
    pass


class Enstaller(object):
    """ enpkg back-end

    Holds the state and includes methods to do all the work of an
    invocation of enpkg. Can also be used as a programmatic interface
    to the same functionality as enpkg.
    """
    def __init__(self, chain, prefixes=None, dry_run=False):
        self.chain = chain
        self.prefixes = prefixes or [sys.prefix]
        self.dry_run = dry_run
        self.egg_dir = config.get('local',
                                  join(self.prefixes[0], 'LOCAL-REPO'))


        # Callback to be called before an install/remove is done
        #
        # Signature should be callback(enst, pkgs, action)
        #   enst: This Enstaller instance
        #   pkgs: a list of packages to be installed (dists)
        #   action: 'install' or 'remove'
        self.pre_install_callback = None

        # Callback to be called with download status of an individual
        # egg
        self.download_progress_callback = None

        # Callback to be called with install status of an individual
        # egg
        self.install_progress_callback = None

        # Callback to be called immediately before an individual
        # package is downloaded, copied, installed, removed
        #
        # Signature should be callback(egg_name, action)
        #   egg_name: name of the egg being installed
        #   action: 'copying', 'downloading', 'installing', 'removing'
        self.file_action_callback = None

    def path_commands(self):
        commands = []
        cmd = ('export', 'set')[sys.platform == 'win32']
        # Set PATH
        commands.append("%s PATH=%s" % (cmd, os.pathsep.join(
            join(p, bin_dir_name) for p in self.prefixes)))

        # Set PYTHONPATH, if needed
        if self.prefixes != [sys.prefix]:
            commands.append("%s PYTHONPATH=%s" % (cmd, os.pathsep.join(
                join(prefix, rel_site_packages) for prefix in self.prefixes)))

        # Set *_LIBRARY_PATH, as needed
        if sys.platform != 'win32':
            if sys.platform == 'darwin':
                name = 'DYLD_LIBRARY_PATH'
            else:
                name = 'LD_LIBRARY_PATH'
            commands.append("%s %s=%s" % (cmd, name, os.pathsep.join(
                join(p, 'lib') for p in self.prefixes)))

        return commands

    def can_write_prefix(self):
        prefix = self.prefixes[0]
        path = join(prefix, 'hello.txt')
        try:
            if not isdir(prefix):
                os.makedirs(prefix)
            open(path, 'w').write('Hello World!\n')
        except:
            return False
        finally:
            if isfile(path):
                os.unlink(path)

        return True

    def get_installed_info(self, cname):
        return [(prefix, get_installed_info(prefix, cname))
                for prefix in self.prefixes]

    def get_installed_cnames(self):
        cnames = []
        for prefix in self.prefixes:
            cnames.extend(egginst.get_installed_cnames(prefix))
        return cnames

    def get_installed_eggs(self):
        eggs = []
        for cname in self.get_installed_cnames():
            for prefix, info in self.get_installed_info(cname):
                if info:
                    eggs.append(info['egg_name'])
        return eggs

    def get_dist_meta(self, req):
        dist = self.chain.get_dist(req)
        if dist:
            return self.chain.index[dist]
        else:
            return None

    def get_dependencies(self):
        if not getattr(self, '_dependencies', None):
            egg_info_dir = join(self.prefixes[0], 'EGG-INFO')
            if not isdir(egg_info_dir):
                return {}
            res = {}
            for dn in os.listdir(egg_info_dir):
                path = join(egg_info_dir, dn, 'spec', 'depend')
                if isfile(path):
                    spec = parse_data(open(path).read())
                    add_Reqs_to_spec(spec)
                    res[spec['cname']] = spec
            self._dependencies = res
        return self._dependencies

    def set_chain_callbacks(self):
        self.chain.file_action_callback = self.file_action_callback
        self.chain.download_progress_callback = self.download_progress_callback

    def egginst_subprocess(egg_path, action):
        pass

    def install_egg(self, dist):
        repo, eggname = dist_naming.split_dist(dist)
        pkg_path = join(self.egg_dir, eggname)
        if (sys.platform == 'win32' and
            eggname.lower().startswith(('appinst-', 'pywin32-'))):
            self.egginst_subprocess(pkg_path, 'install')
            return
        self.file_action_callback(eggname, 'installing')
        if self.dry_run:
            return
        ei = egginst.EggInst(pkg_path, self.prefixes[0],
                             noapp=config.get('noapp'))
        ei.progress_callback = console_file_progress
        ei.install()
        info = self.get_installed_info(cname_fn(eggname))
        path = join(info['meta_dir'], '__enpkg__.txt')
        with open(path, 'w') as f:
            f.write('repo = %r\n' % repo)

    def remove_egg(self, eggname):
        if (sys.platform == 'win32' and
            eggname.lower().startswith(('appinst-', 'pywin32-'))):
            self.egginst_subprocess(eggname, 'remove')
            return
        self.file_action_callback(eggname, 'removing')
        if self.dry_run:
            return
        ei = egginst.EggInst(eggname, self.prefixes[0],
                             noapp=config.get('noapp'))
        ei.progress_callback = console_file_progress
        ei.remove()

    def install(self, req, mode='recur', force=False, force_all=False):
        dists = self.chain.install_sequence(req, mode)
        if not dists:
            raise DistributionNotFound(
                "No distribution found for requirement '%s'" % req)

        if self.pre_install_callback:
            self.pre_install_callback(self, dists, 'install')

        # Get eggname for each dist, since it's used so much
        dists = [(dist, dist_naming.filename_dist(dist))
                 for dist in dists]

        # packages which are intalled currently
        all_inst = set(self.get_installed_eggs())

        # packages being excluded from being installed
        if force_all:
            exclude = set()
        else:
            exclude = all_inst
            if force:
                exclude.discard(dist_naming.filename_dist(dists[-1]))

        self.set_chain_callbacks()

        # fetch distributions
        if not isdir(self.egg_dir):
            os.makedirs(self.egg_dir)
        for dist, eggname in dists:
            if eggname in exclude:
                continue
            self.chain.fetch_dist(dist, self.egg_dir, check_md5=force or force_all,
                                  dry_run=self.dry_run)

        # remove packages (in reverse install order)
        for dist, eggname in reversed(dists):
            # Don't remove the file if it's already the right version
            if eggname in all_inst:
                continue

            # Get the currently installed version, to remove
            info = self.get_installed_info(cname_fn(eggname))[0][1]
            eggname = info['egg_name']
            if not eggname:
                continue
            self.remove_egg(eggname)

        # install packages
        installed_count = 0
        for dist, eggname in dists:
            if eggname in exclude:
                continue
            self.install_egg(dist)
            installed_count += 1
        return installed_count

    def remove(self, req):
        d = self.get_installed_info(req.name)[0][1]
        if not d:
            raise DistributionNotFound(
                "Package %r does not seem to be installed." % req.name)
        pkg = d['egg_name'][:-4]
        if req.version:
            v_a, b_a = pkg.split('-')[1:3]
            if req.version != v_a or (req.build and req.build != int(b_a)):
                raise DistributionVersionMismatch(
                    "Version mismatch: %s is installed cannot remove %s." %
                    (pkg, req))
        if self.pre_install_callback:
            dist = self.chain.get_dist(req)
            self.pre_install_callback(self, [dist], 'remove')
        self.remove_egg(d['egg_name'])


def print_path(enst):
    print "Prefixes:"
    for p in enst.prefixes:
        print '    %s%s' % (p, ['', ' (sys)'][p == sys.prefix])
    print

    for command in enst.path_commands():
        print command


def check_write(enst):
    if not enst.can_write_prefix():
        print "ERROR: Could not write simple file into:", enst.prefixes[0]
        sys.exit(1)


def print_installed_info(enst, cname):
    for prefix, info in enst.get_installed_info(cname):
        if prefix == sys.prefix and len(enst.prefixes) > 1:
            if info is None:
                print "%s is not installed in sys.prefix" % cname
            else:
                print "%(egg_name)s was installed in sys.prefix on: %(mtime)s"\
                    % info
        else:
            if info is None:
                print "%s is not installed" % cname
            else:
                print "%(egg_name)s was installed on: %(mtime)s" % info


def info_option(enst, cname):
    info = get_info()
    if info and cname in info:
        spec = info[cname]
        print "Name    :", spec['name']
        print "License :", spec['license']
        print "Summary :", spec['summary']
        print
        for line in textwrap.wrap(' '.join(spec['description'].split()), 77):
            print line
    print
    print "In repositories:"
    displayed = set()
    for dist in enst.chain.iter_dists(Req(cname)):
        repo = dist_naming.repo_dist(dist)
        if repo not in displayed:
            print '    %s' % repo
            displayed.add(repo)
    print

    dist = enst.chain.get_dist(Req(cname))
    if dist:
        reqs = set(r.name for r in enst.chain.reqs_dist(dist))
        print "Requirements: %s" % ', '.join(sorted(reqs))

    print "Available versions: %s" % ', '.join(enst.chain.list_versions(cname))
    print_installed_info(enst, cname)


def print_installed(group):
    fmt = '%-20s %-20s %s'
    print fmt % ('Project name', 'Version', 'Repository')
    print 60 * '='
    for prefix, info in group:
        if info is None:
            continue
        print fmt % (info['name'], info['version'], info.get('repo', '-'))


def list_option(enst, pat):
    info_groups = zip(*[enst.get_installed_info(cname)
                        for cname in enst.get_installed_cnames()
                        if not pat or pat.search(cname)])
    for group in reversed(info_groups):
        prefix = group[0][0]
        if prefix == sys.prefix:
            print 'sys.prefix:', prefix
        else:
            print 'prefix:', prefix
        print_installed(group)


def whats_new(enst):
    fmt = '%-25s %-15s %s'
    print fmt % ('Name', 'installed', 'available')
    print 60 * "="

    inst = set(enst.get_installed_eggs())

    something_new = False
    for egg_name in inst:
        if not dist_naming.is_valid_eggname(egg_name):
            continue
        in_n, in_v, in_b = dist_naming.split_eggname(egg_name)
        spec = enst.get_dist_meta(Req(in_n))
        if spec is None:
            continue
        av_v = spec['version']
        if (av_v != in_v and
                    comparable_version(av_v) > comparable_version(in_v)):
            print fmt % (in_n, in_v, av_v)
            something_new = True

    if not something_new:
        print "no new version of any installed package is available"


def search(enst, pat=None):
    """
    Print the distributions available in a repo, i.e. a "virtual" repo made
    of a chain of (indexed) repos.
    """
    fmt = "%-25s %-15s %s"
    print fmt % ('Project name', 'Versions', 'Repository')
    print 55 * '-'

    for name in sorted(enst.chain.groups.keys(), key=string.lower):
        if pat and not pat.search(name):
            continue
        versions = enst.chain.list_versions(name)
        disp_name = name
        for version in versions:
            req = Req(name + ' ' + version)
            dist = enst.chain.get_dist(req)
            repo = dist_naming.repo_dist(dist)
            print fmt % (disp_name, version,  shorten_repo(repo))
            disp_name = ''


def depend_warn(enst, dists, action):
    """
    Warns the user about packages to be changed (i.e. removed or updated),
    if other packages depend on the package.

    Warnings are printed when the required name of the package matches.
    The ignore_version option determines if a version comparison is also
    desired as well, which it is not for the --remove option, since when
    a package is removed it does not matter which version is required.
    Hence, in remove_req() this function is called with ignore_version=True.
    """
    if action == 'remove':
        ignore_version = True
    else:
        ignore_version = False
    pkgs = [dist_naming.filename_dist(d) for d in dists]

    names = {}
    for pkg in pkgs:
        names[cname_fn(pkg)] = pkg
    index = enst.get_dependencies()
    for spec in index.itervalues():
        if spec['cname'] in names:
            continue
        for req in spec["Reqs"]:
            if req.name not in names:
                continue
            if (ignore_version or
                     (req.version and
                      req.version != names[req.name].split('-')[1])):
                print "Warning: %s depends on %s" % (spec_as_req(spec), req)


def verbose_depend_warn(enst, dists, action):
    if dists:
        print 'Distributions in install sequence:'
        for d in dists:
            print '    ' + d
    depend_warn(enst, dists, action)


def remove_req(enst, req):
    """
    Tries remove a package from prefix given a requirement object.
    This function is only used for the --remove option.
    """
    try:
        enst.remove(req)
    except DistributionNotFound as e:
        print e.message
        return
    except DistributionVersionMismatch as e:
        print e.message
        return


def check_available(cname):
    avail = get_available()
    if cname not in avail:
        return False
    print """
But wait, %r is available in the EPD subscriber repository!
Would you like to go to %r
to subscribe?
""" % (cname, config.upgrade_epd_url)
    answer = raw_input('[yes|no]> ').strip().lower()
    if answer not in ('y', 'yes'):
        return False
    print """
Once you have obtained a subscription, you can proceed here.
"""
    import webbrowser
    webbrowser.open(config.upgrade_epd_url)
    config.write()
    return True


def add_url(url, verbose):
    url = dist_naming.cleanup_reponame(url)

    arch_url = config.arch_filled_url(url)
    Chain([arch_url], verbose)

    if arch_url in config.get('IndexedRepos'):
        print "Already configured:", url
        return

    config.prepend_url(url)


def revert(enst, rev_in):
    history = History(enst.prefixes[0])
    try:
        rev = int(rev_in)
    except ValueError:
        # we have a "date string"
        from parse_dt import parse
        rev = parse(rev_in)
        if rev is None:
            sys.exit("Error: could not parse: %r" % rev_in)

    print "reverting to: %r" % rev
    try:
        state = history.get_state(rev)
    except IndexError:
        sys.exit("Error: no such revision: %r" % rev)

    curr = set(egginst.get_installed())
    if state == curr:
        print "Nothing to revert"
        return

    # remove packages
    for fn in curr - state:
        enst.remove_egg(fn)

    # install packages (fetch from server if necessary)
    to_install = []
    need_fetch = []
    for fn in state - curr:
        to_install.append(fn)
        if not isfile(join(enst.egg_dir, fn)):
            need_fetch.append(fn)
    if need_fetch:
        for fn in need_fetch:
            dist = enst.chain.get_dist(filename_as_req(fn))
            if dist:
                enst.chain.fetch_dist(dist, enst.egg_dir,
                                      dry_run=enst.dry_run)
    for fn in to_install:
        pprint_fn_action(fn, 'installing')
        egg_path = join(enst.egg_dir, fn)
        if isfile(egg_path):
            ei = egginst.EggInst(egg_path)
            ei.progress_callback = console_file_progress
            ei.install()

    history.update()


def iter_dists_excl(dists, exclude_fn):
    """
    Iterates over all dists, excluding the ones whose filename is an element
    of exclude_fn.  Yields the distribution.
    """
    for dist in dists:
        fn = dist_naming.filename_dist(dist)
        if fn in exclude_fn:
            continue
        yield dist


def install_req(enst, req, opts):
    try:
        installed = enst.install(req, 'root' if opts.no_deps else 'recur',
                                 opts.force, opts.forceall)
    except DistributionNotFound as e:
        print e.message
        versions = enst.chain.list_versions(req.name)
        if versions:
            print "Versions for package %r are: %s" % (req.name,
                                                       ', '.join(versions))
        info = enst.get_installed_info(req.name)[0][1]
        if info:
            print "%(egg_name)s was installed on: %(mtime)s" % info
        elif 'EPD_free' in sys.version:
            check_available(req.name)
        sys.exit(1)

    if not installed:
        print "No update necessary, %s is up-to-date." % req
        print_installed_info(enst, req.name)


def main():
    # REMOVE THIS AFTER DONE TESTING
    sys.argv[0] = 'enpkg'
    # usage="usage: %prog [options] [name] [version]",
    p = ArgumentParser(description=__doc__)
    p.add_argument('cnames', metavar='CNAME', nargs='*',
                   help='package(s) to work on')
    p.add_argument("--add-url", metavar='URL',
                   help="add a repository URL to the configuration file")
    p.add_argument("--config", action="store_true",
                   help="display the configuration and exit")
    p.add_argument('-f', "--force", action="store_true",
                   help="force install the main package "
                        "(not it's dependencies, see --forceall)")
    p.add_argument("--forceall", action="store_true",
                   help="force install of all packages "
                        "(i.e. including dependencies)")
    p.add_argument('-i', "--info", action="store_true",
                   help="show information about a package")
    p.add_argument("--log", action="store_true", help="print revision log")
    p.add_argument('-l', "--list", action="store_true",
                   help="list the packages currently installed on the system")
    p.add_argument('-n', "--dry-run", action="store_true",
                   help="show what would have been downloaded/removed/installed")
    p.add_argument('-N', "--no-deps", action="store_true",
                   help="neither download nor install dependencies")
    p.add_argument("--path", action="store_true",
                   help="based on the configuration, display how to set the "
                        "PATH and PYTHONPATH environment variables")
    p.add_argument("--prefix", metavar='PATH',
                   help="install prefix (disregarding of any settings in "
                        "the config file)")
    p.add_argument("--proxy", metavar='URL', help="use a proxy for downloads")
    p.add_argument("--remove", action="store_true", help="remove a package")
    p.add_argument("--revert", metavar="REV",
                   help="revert to a previous set of packages")
    p.add_argument('-s', "--search", action="store_true",
                   help="search the index in the repo (chain) of packages "
                        "and display versions available.")
    p.add_argument("--sys-config", action="store_true",
                   help="use <sys.prefix>/.enstaller4rc (even when "
                        "~/.enstaller4rc exists")
    p.add_argument("--sys-prefix", action="store_true",
                   help="use sys.prefix as the install prefix")
    p.add_argument("--userpass", action="store_true",
                   help="change EPD authentication in configuration file")
    p.add_argument('-v', "--verbose", action="store_true")
    p.add_argument('--version', action="version",
                   version='enstaller version: ' + __version__)
    p.add_argument("--whats-new", action="store_true",
                   help="display to which installed packages updates are "
                        "available")
    args = p.parse_args()

    if len(args.cnames) > 0 and (args.config or args.path or args.userpass or
                                 args.revert or args.log or args.whats_new):
        p.error("Option takes no arguments")

    if args.prefix and args.sys_prefix:
        p.error("Options --prefix and --sys-prefix exclude each ohter")

    if args.force and args.forceall:
        p.error("Options --force and --forceall exclude each ohter")

    pat = None
    if (args.list or args.search) and args.cnames:
        pat = re.compile(args.cnames[0], re.I)

    if args.sys_prefix:
        prefix = sys.prefix
    elif args.prefix:
        prefix = args.prefix
    else:
        prefix = config.get('prefix')
    if prefix == sys.prefix:
        prefixes = [prefix]
    else:
        prefixes = [prefix, sys.prefix]

    if args.log:                                  # --log
        History(prefix).print_log()
        return

    if args.sys_config:                           # --sys-config
        config.get_path = lambda: config.system_config_path

    if args.config:                               # --config
        config.print_config()
        return

    if args.userpass:                             # --userpass
        config.change_auth()
        return

    if args.proxy:                                # --proxy
        setup_proxy(args.proxy)
    elif config.get('proxy'):
        setup_proxy(config.get('proxy'))
    else:
        setup_proxy()

    dry_run = args.dry_run
    verbose = args.verbose

    enst = Enstaller(chain=Chain(config.get('IndexedRepos'), args.verbose),
                     prefixes=prefixes, dry_run=dry_run)
    if args.verbose:
        enst.pre_install_callback = verbose_depend_warn
    else:
        enst.pre_install_callback = depend_warn
    enst.file_action_callback = pprint_fn_action
    enst.download_progress_callback = console_file_progress
    enst.install_progress_callback = console_file_progress

    if args.add_url:                              # --add-url
        add_url(args.add_url, args.verbose)
        return

    if args.path:                                 # --path
        print_path(enst)
        return

    if args.list:                                 # --list
        list_option(enst, pat)
        return

    if args.revert:                               # --revert
        revert(enst, args.revert)
        return

    if args.search:                               # --search
        search(enst, pat)
        return

    if args.info:                                 # --info
        if len(args.cnames) != 1:
            p.error("Option requires one argument (name of package)")
        info_option(enst, canonical(args.cnames[0]))
        return

    if args.whats_new:                            # --whats-new
        whats_new(enst)
        return

    if len(args.cnames) == 0:
        p.error("Requirement(s) missing")
    elif len(args.cnames) == 2:
        pat = re.compile(r'\d+\.\d+')
        if pat.match(args.cnames[1]):
            args.cnames = ['-'.join(args.cnames)]

    reqs = []
    for arg in args.cnames:
        if '-' in arg:
            name, version = arg.split('-', 1)
            reqs.append(Req(name + ' ' + version))
        else:
            reqs.append(Req(arg))

    if verbose:
        print "Requirements:"
        for req in reqs:
            print '    %r' % req
        print

    print "prefix:", prefix
    check_write(enst)

    with History(prefix):
        for req in reqs:
            if args.remove:                           # --remove
                remove_req(enst, req)
            else:
                install_req(enst, req, args)


if __name__ == '__main__':
    main()
