# Author: Ilan Schnell <ischnell@enthought.com>
"""\
enstaller is a managing tool for egginst-based installs, and the CLI is
called enpkg which calls out to egginst to do the actual install.
enpkg can access distributions from local and HTTP repositories.
"""
import os
import re
import sys
import site
import string
import textwrap
from argparse import ArgumentParser
from os.path import isfile, join

import egginst
from egginst.utils import bin_dir_name, rel_site_packages
from enstaller import __version__
import config
from history import History
from proxy.api import setup_proxy
from utils import comparable_version, abs_expanduser, fill_url

from eggcollect import EggCollection
from enpkg import Enpkg, EnpkgError, create_joined_store
from resolve import Req


FMT = '%-20s %-15s %s'


def env_option(prefixes):
    print "Prefixes:"
    for p in prefixes:
        print '    %s%s' % (p, ['', ' (sys)'][p == sys.prefix])
    print

    cmd = ('export', 'set')[sys.platform == 'win32']
    print "%s PATH=%s" % (cmd, os.pathsep.join(
                                 join(p, bin_dir_name) for p in prefixes))
    if len(prefixes) > 1:
        print "%s PYTHONPATH=%s" % (cmd, os.pathsep.join(
                            join(p, rel_site_packages) for p in prefixes))

    if sys.platform != 'win32':
        if sys.platform == 'darwin':
            name = 'DYLD_LIBRARY_PATH'
        else:
            name = 'LD_LIBRARY_PATH'
        print "%s %s=%s" % (cmd, name, os.pathsep.join(
                                 join(p, 'lib') for p in prefixes))


def disp_store_info(info):
    sl = info.get('store_location')
    if not sl:
        return '-'
    for rm in 'http://', 'https://', 'www', '.enthought.com', '/repo/':
        sl = sl.replace(rm, '')
    return sl.replace('/eggs/', ' ').strip('/')


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

    print "Available versions: %s" % ', '.join(chain.list_versions(cname))
    print_installed_info(enst, cname)


def print_installed(prefix, hook=False, pat=None):
    print FMT % ('Name', 'Version', 'Store')
    print 60 * '='
    ec = EggCollection(prefix, hook)
    for egg, info in ec.query():
        if pat and not pat.search(info['name']):
            continue

        print FMT % (info['name'], '%(version)s-%(build)d' % info,
                     disp_store_info(info))


def list_option(prefixes, hook=False, pat=None):
    for prefix in reversed(prefixes):
        print "prefix:", prefix
        print_installed(prefix, hook, pat)
        print


def imports_option(enpkg, pat=None):
    print FMT % ('Name', 'Version', 'Location')
    print 60 * "="

    names = set(info['name'] for _, info in enpkg.query_installed())
    for name in sorted(names, key=string.lower):
        if pat and not pat.search(name):
            continue
        for c in reversed(enpkg.ec.collections):
            index = dict(c.query(name=name))
            if index:
                info = index.values()[0]
                loc = 'sys' if c.prefix == sys.prefix else 'user'
        print FMT % (name, '%(version)s-%(build)d' % info, loc)


def search(enpkg, pat=None):
    """
    Print the distributions available in a repo, i.e. a "virtual" repo made
    of a chain of (indexed) repos.
    """
    print FMT % ('Name', 'Versions', 'Repository')
    print 60 * '-'

    names = set(info['name'] for _, info in enpkg.query_remote())
    for name in sorted(names, key=string.lower):
        if pat and not pat.search(name):
            continue
        disp_name = name
        for info in enpkg.info_list_name(name):
            print FMT % (disp_name, '%(version)s-%(build)d' % info,
                         disp_store_info(info))
            disp_name = ''


def whats_new(enst):
    print FMT % ('Name', 'installed', 'available')
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
            print FMT % (in_n, in_v, av_v)
            something_new = True

    if not something_new:
        print "no new version of any installed package is available"


def remove_req(enpkg, req):
    """
    Tries remove a package from prefix given a requirement object.
    This function is only used for the --remove option.
    """
    try:
        enpkg.remove(req)
    except EnpkgError as e:
        print e.message
        return


def add_url(url, verbose):
    url = dist_naming.cleanup_reponame(url)

    arch_url = config.arch_filled_url(url)
    Chain([arch_url], verbose)

    if arch_url in config.get('IndexedRepos'):
        print "Already configured:", url
        return

    config.prepend_url(url)


def revert(enst, rev_in, quiet=False):
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
        egg_path = join(enst.egg_dir, fn)
        if isfile(egg_path):
            ei = egginst.EggInst(egg_path)
            ei.install()

    history.update()


def install_req(enpkg, req, opts):
    try:
        cnt = enpkg.install(req, mode='root' if opts.no_deps else 'recur',
                            force=opts.force, forceall=opts.forceall)
    except EnpkgError, e:
        print e.message
        info_list = enpkg.info_list_name(req.name)
        if info_list:
            print "Versions for package %r are: %s" % (
                req.name,
                ', '.join(sorted(set(i['version'] for i in info_list))))
        sys.exit(1)

    if cnt == 0:
        print "No update necessary, %r is up-to-date." % req.name
        #print_installed_info(enpkg, req.name)


def main():
    try:
        user_base = site.USER_BASE
    except AttributeError:
        user_base = abs_expanduser('~/.local')

    p = ArgumentParser(description=__doc__)
    p.add_argument('cnames', metavar='NAME', nargs='*',
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
    p.add_argument("--hook", action="store_true",
                   help="don't install into site-packages (experimental)")
    p.add_argument("--imports", action="store_true",
                   help="show which packages can be imported")
    p.add_argument('-i', "--info", action="store_true",
                   help="show information about a package")
    p.add_argument("--log", action="store_true", help="print revision log")
    p.add_argument('-l', "--list", action="store_true",
                   help="list the packages currently installed on the system")
    p.add_argument('-n', "--dry-run", action="store_true",
               help="show what would have been downloaded/removed/installed")
    p.add_argument('-N', "--no-deps", action="store_true",
                   help="neither download nor install dependencies")
    p.add_argument("--env", action="store_true",
                   help="based on the configuration, display how to set the "
                        "some environment variables")
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
                        "~/.enstaller4rc exists)")
    p.add_argument("--sys-prefix", action="store_true",
                   help="use sys.prefix as the install prefix")
    p.add_argument("--user", action="store_true",
               help="install into user prefix, i.e. --prefix=%r" % user_base)
    p.add_argument("--userpass", action="store_true",
                   help="change EPD authentication in configuration file")
    p.add_argument('-v', "--verbose", action="store_true")
    p.add_argument('--version', action="version",
                   version='enstaller version: ' + __version__)
    p.add_argument("--whats-new", action="store_true",
                   help="display to which installed packages updates are "
                        "available")
    args = p.parse_args()

    if len(args.cnames) > 0 and (args.config or args.env or args.userpass or
                                 args.revert or args.log or args.whats_new):
        p.error("Option takes no arguments")

    if args.user:
        args.prefix = user_base

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
        prefix = config.get('prefix', sys.prefix)

    if prefix == sys.prefix:
        prefixes = [sys.prefix]
    else:
        prefixes = [prefix, sys.prefix]

    if args.env:                                  # --env
        env_option(prefixes)
        return

    if args.log:                                  # --log
        History(prefix).print_log()
        return

    if args.sys_config:                           # --sys-config
        config.get_path = lambda: config.system_config_path

    if args.config:                               # --config
        config.print_config()
        return

    if args.userpass:                             # --userpass
        username, password = config.input_auth()
        config.change_auth(username, password)
        return

    if args.list:                                 # --list
        list_option(prefixes, args.hook, pat)
        return

    if args.proxy:                                # --proxy
        setup_proxy(args.proxy)
    elif config.get('proxy'):
        setup_proxy(config.get('proxy'))
    else:
        setup_proxy()

    dry_run = args.dry_run
    verbose = args.verbose

    if 0: # for testing event manager only
        from encore.events.api import EventManager
        from encore.terminal.api import ProgressDisplay
        evt_mgr = EventManager()
        display = ProgressDisplay(evt_mgr)
    else:
        evt_mgr = None

    if config.get_path() is None or config.get('use_webservice'):
        urls = ['http://beta.enthought.com/webservice/epd/{SUBDIR}/']
    else:
        urls = config.get('IndexedRepos')
    urls = [fill_url(u) for u in urls]

    enpkg = Enpkg(create_joined_store(urls),
                  config.get_auth(), prefixes=prefixes, hook=args.hook,
                  evt_mgr=evt_mgr, verbose=args.verbose)

    if args.imports:                              # --imports
        assert not args.hook
        imports_option(enpkg, pat)
        return

    if args.add_url:                              # --add-url
        add_url(args.add_url, args.verbose)
        return

    if args.revert:                               # --revert
        revert(enst, args.revert)
        return

    if args.search:                               # --search
        search(enpkg, pat)
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

    with History(prefix):
        for req in reqs:
            if args.remove:                           # --remove
                remove_req(enpkg, req)
            else:
                install_req(enpkg, req, args)


if __name__ == '__main__':
    main()
