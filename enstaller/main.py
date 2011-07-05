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
from os.path import basename, isdir, isfile, join
from optparse import OptionParser

import egginst
from egginst.utils import bin_dir_name, rel_site_packages, pprint_fn_action

import config
from proxy.api import setup_proxy
from utils import (canonical, cname_fn, get_info, comparable_version,
                   shorten_repo, get_installed_info, get_available)
from indexed_repo import (Chain, Req, add_Reqs_to_spec, spec_as_req,
                          parse_data, dist_naming)


# global options variables
prefix = None
dry_run = None
verbose = None

c = None
def set_chain():
    global c
    c = Chain(config.get('IndexedRepos'), verbose)


def print_path():
    prefixes = [sys.prefix]
    if prefix != sys.prefix:
        prefixes.insert(0, prefix)
    print "Prefixes:"
    for p in prefixes:
        print '    %s%s' % (p, ['', ' (sys)'][p == sys.prefix])
    print

    cmd = ('export', 'set')[sys.platform == 'win32']
    print "%s PATH=%s" % (cmd, os.pathsep.join(
                                 join(p, bin_dir_name) for p in prefixes))
    if prefix != sys.prefix:
        print "%s PYTHONPATH=%s" % (cmd, join(prefix, rel_site_packages))

    if sys.platform != 'win32':
        if sys.platform == 'darwin':
            name = 'DYLD_LIBRARY_PATH'
        else:
            name = 'LD_LIBRARY_PATH'
        print "%s %s=%s" % (cmd, name, os.pathsep.join(
                                 join(p, 'lib') for p in prefixes))


def egginst_subprocess(pkg_path, remove):
    # only used on Windows
    path = join(sys.prefix, bin_dir_name, 'egginst-script.py')
    args = [sys.executable, path, '--prefix', prefix]
    if dry_run:
        args.append('--dry-run')
    if remove:
        args.append('--remove')
    if config.get('noapp'):
        args.append('--noapp')
    args.append(pkg_path)
    if verbose:
        print 'CALL: %r' % args
    subprocess.call(args)


def egginst_remove(pkg):
    fn = basename(pkg)
    if (sys.platform == 'win32'  and
            fn.lower().startswith(('appinst-', 'pywin32-'))):
        if verbose:
            print "Starting subprocess:"
        egginst_subprocess(pkg, remove=True)
        return
    pprint_fn_action(fn, 'removing')
    if dry_run:
        return
    ei = egginst.EggInst(pkg, prefix, noapp=config.get('noapp'))
    ei.remove()


def egginst_install(dist):
    repo, fn = dist_naming.split_dist(dist)
    pkg_path = join(config.get('local'), fn)
    if (sys.platform == 'win32'  and
            fn.lower().startswith(('appinst-', 'pywin32-'))):
        if verbose:
            print "Starting subprocess:"
        egginst_subprocess(pkg_path, remove=False)
        return
    pprint_fn_action(fn, 'installing')
    if dry_run:
        return
    ei = egginst.EggInst(pkg_path, prefix, noapp=config.get('noapp'))
    ei.install()
    info = get_installed_info(prefix, cname_fn(fn))
    path = join(info['meta_dir'], '__enpkg__.txt')
    fo = open(path, 'w')
    fo.write("repo = %r\n" % repo)
    fo.close()


def check_write():
    if not isdir(prefix):
        os.makedirs(prefix)
    path = join(prefix, 'hello.txt')
    try:
        open(path, 'w').write('Hello World!\n')
    except:
        print "ERROR: Could not write simple file into:", prefix
        sys.exit(1)
    finally:
        if isfile(path):
            os.unlink(path)


def print_installed_info(cname):
    info = get_installed_info(prefix, cname)
    if info is None:
        print "%s is not installed" % cname
    else:
        print "%(egg_name)s was installed on: %(mtime)s" % info

    if prefix == sys.prefix:
        return

    info = get_installed_info(sys.prefix, cname)
    if info is None:
        print "%s is not installed in sys.prefix" % cname
    else:
        print "%(egg_name)s was installed in sys.prefix on: %(mtime)s" % info


def info_option(cname):
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
    for dist in c.iter_dists(Req(cname)):
        repo = dist_naming.repo_dist(dist)
        if repo not in displayed:
            print '    %s' % repo
            displayed.add(repo)
    print

    dist = c.get_dist(Req(cname))
    if dist:
        reqs = set(r.name for r in c.reqs_dist(dist))
        print "Requirements: %s" % ', '.join(sorted(reqs))

    print "Available versions: %s" % ', '.join(c.list_versions(cname))
    print_installed_info(cname)


def print_installed(prefix, pat=None):
    fmt = '%-20s %-20s %s'
    print fmt % ('Project name', 'Version', 'Repository')
    print 60 * '='
    for cname in egginst.get_installed_cnames(prefix):
        if pat and not pat.search(cname):
            continue
        info = get_installed_info(prefix, cname)
        if info is None:
            continue
        print fmt % (info['name'], info['version'], info.get('repo', '-'))


def list_option(pat):
    print "sys.prefix:", sys.prefix
    print_installed(sys.prefix, pat)
    if prefix == sys.prefix:
        return
    print
    print "prefix:", prefix
    print_installed(prefix, pat)


def whats_new():
    fmt = '%-25s %-15s %s'
    print fmt % ('Name', 'installed', 'available')
    print 60* "="

    inst = set(egginst.get_installed(sys.prefix))
    if prefix != sys.prefix:
        inst |= set(egginst.get_installed(prefix))

    something_new = False
    for egg_name in inst:
        if not dist_naming.is_valid_eggname(egg_name):
            continue
        in_n, in_v, in_b = dist_naming.split_eggname(egg_name)
        dist = c.get_dist(Req(in_n))
        if dist is None:
            continue
        av_v = c.index[dist]['version']
        if (av_v != in_v and
                    comparable_version(av_v) > comparable_version(in_v)):
            print fmt % (in_n, in_v, av_v)
            something_new = True

    if not something_new:
        print "no new version of any installed package is available"


def search(pat=None):
    """
    Print the distributions available in a repo, i.e. a "virtual" repo made
    of a chain of (indexed) repos.
    """
    fmt = "%-25s %-15s %s"
    print fmt % ('Project name', 'Versions', 'Repository')
    print 55 * '-'

    for name in sorted(c.groups.keys(), key=string.lower):
        if pat and not pat.search(name):
            continue
        versions = c.list_versions(name)
        disp_name = name
        for version in versions:
            req = Req(name + ' ' + version)
            dist = c.get_dist(req)
            repo = dist_naming.repo_dist(dist)
            print fmt % (disp_name, version,  shorten_repo(repo))
            disp_name = ''


def read_depend_files():
    """
    Returns a dictionary mapping canonical project names to the spec
    dictionaries of the installed packages.
    """
    egg_info_dir = join(prefix, 'EGG-INFO')
    if not isdir(egg_info_dir):
        return {}
    res = {}
    for dn in os.listdir(egg_info_dir):
        path = join(egg_info_dir, dn, 'spec', 'depend')
        if isfile(path):
            spec = parse_data(open(path).read())
            add_Reqs_to_spec(spec)
            res[spec['cname']] = spec
    return res


def depend_warn(pkgs, ignore_version=False):
    """
    Warns the user about packages to be changed (i.e. removed or updated),
    if other packages depend on the package.

    Warnings are printed when the required name of the package matches.
    The ignore_version option determines if a version comparison is also
    desired as well, which it is not for the --remove option, since when
    a package is removed it does not matter which version is required.
    Hence, in remove_req() this function is called with ignore_version=True.
    """
    names = {}
    for pkg in pkgs:
        names[cname_fn(pkg)] = pkg
    index = read_depend_files()
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


def remove_req(req):
    """
    Tries remove a package from prefix given a requirement object.
    This function is only used for the --remove option.
    """
    d = get_installed_info(prefix, req.name)
    if not d:
        print "Package %r does not seem to be installed." % req.name
        return
    pkg = d['egg_name'][:-4]
    if req.version:
        v_a, b_a = pkg.split('-')[1:3]
        if req.version != v_a or (req.build and req.build != int(b_a)):
            print("Version mismatch: %s is installed cannot remove %s." %
                  (pkg, req))
            return
    depend_warn([pkg], ignore_version=True)
    egginst_remove(pkg)


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


def get_dists(req, mode):
    """
    resolve the requirement
    """
    dists = c.install_sequence(req, mode)
    if dists:
        if verbose:
            print "Distributions in install sequence:"
            for d in dists:
                print '    ' + d
        return dists

    print "No distribution found for requirement '%s'." % req
    versions = c.list_versions(req.name)
    if versions:
        print "Versions for package %r are: %s" % (req.name,
                                                   ', '.join(versions))
    info = get_installed_info(prefix, req.name)
    if info:
        print "%(egg_name)s was installed on: %(mtime)s" % info
    elif 'EPD_free' in sys.version:
        if check_available(req.name):
            set_chain()
            return get_dists(req, mode)
    sys.exit(1)


def add_url(url):
    url = dist_naming.cleanup_reponame(url)

    arch_url = config.arch_filled_url(url)
    Chain([arch_url], verbose)

    if arch_url in config.get('IndexedRepos'):
        print "Already configured:", url
        return

    config.prepend_url(url)


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


def main():
    p = OptionParser(usage="usage: %prog [options] [name] [version]",
                     description=__doc__)

    p.add_option("--add-url",
                 action="store",
                 help="add a repository URL to the configuration file",
                 metavar='URL')

    p.add_option("--config",
                 action="store_true",
                 help="display the configuration and exit")

    p.add_option('-f', "--force",
                 action="store_true",
                 help="force install the main package "
                      "(not it's dependencies, see --forceall)")

    p.add_option("--forceall",
                 action="store_true",
                 help="force install of all packages "
                      "(i.e. including dependencies)")

    p.add_option('-i', "--info",
                 action="store_true",
                 help="show information about a package")

    p.add_option('-l', "--list",
                 action="store_true",
                 help="list the packages currently installed on the system")

    p.add_option('-n', "--dry-run",
                 action="store_true",
                 help="show what would have been downloaded/removed/installed")

    p.add_option('-N', "--no-deps",
                 action="store_true",
                 help="neither download nor install dependencies")

    p.add_option("--path",
                 action="store_true",
                 help="based on the configuration, display how to set the "
                      "PATH and PYTHONPATH environment variables")

    p.add_option("--prefix",
                 action="store",
                 help="install prefix (disregarding of any settings in "
                      "the config file)",
                 metavar='PATH')

    p.add_option("--proxy",
                 action="store",
                 help="use a proxy for downloads",
                 metavar='URL')

    p.add_option("--remove",
                 action="store_true",
                 help="remove a package")

    p.add_option('-s', "--search",
                 action="store_true",
                 help="search the index in the repo (chain) of packages "
                      "and display versions available.")

    p.add_option("--sys-config",
                 action="store_true",
                 help="use <sys.prefix>/.enstaller4rc (even when "
                      "~/.enstaller4rc exists")

    p.add_option("--sys-prefix",
                 action="store_true",
                 help="use sys.prefix as the install prefix")

    p.add_option("--userpass",
                 action="store_true",
                 help="change EPD authentication in configuration file")

    p.add_option('-v', "--verbose", action="store_true")

    p.add_option('--version', action="store_true")

    p.add_option("--whats-new",
                 action="store_true",
                 help="display to which installed packages updates are "
                      "available")

    opts, args = p.parse_args()

    if len(args) > 0 and (opts.config or opts.path or opts.userpass):
        p.error("Option takes no arguments")

    if opts.prefix and opts.sys_prefix:
        p.error("Options --prefix and --sys-prefix exclude each ohter")

    if opts.force and opts.forceall:
        p.error("Options --force and --forceall exclude each ohter")

    pat = None
    if (opts.list or opts.search) and args:
        pat = re.compile(args[0], re.I)

    if opts.version:                              #  --version
        from enstaller import __version__
        print "enstaller version:", __version__
        return

    if opts.sys_config:                           #  --sys-config
        config.get_path = lambda: config.system_config_path

    if opts.config:                               #  --config
        config.print_config()
        return

    if opts.userpass:                             #  --userpass
        config.change_auth()
        return

    #if config.get_path() is None:
    #    # create config file if it dosn't exist
    #    config.write(opts.proxy)

    if opts.proxy:                                #  --proxy
        setup_proxy(opts.proxy)
    elif config.get('proxy'):
        setup_proxy(config.get('proxy'))
    else:
        setup_proxy()

    global prefix, dry_run, version, verbose    #  set globals
    if opts.sys_prefix:
        prefix = sys.prefix
    elif opts.prefix:
        prefix = opts.prefix
    else:
        prefix = config.get('prefix')
    dry_run = opts.dry_run
    verbose = opts.verbose
    version = opts.version

    if opts.add_url:                              #  --add-url
        add_url(opts.add_url)
        return

    if opts.path:                                 #  --path
        print_path()
        return

    if opts.list:                                 #  --list
        list_option(pat)
        return

    set_chain()                                   #  init chain

    if opts.search:                               #  --search
        search(pat)
        return

    if opts.info:                                 #  --info
        if len(args) != 1:
            p.error("Option requires one argument (name of package)")
        info_option(canonical(args[0]))
        return

    if opts.whats_new:                            # --whats-new
        if args:
            p.error("Option requires no arguments")
        whats_new()
        return

    if len(args) == 0:
        p.error("Requirement (name and optional version) missing")
    if len(args) > 2:
        p.error("A requirement is a name and an optional version")
    req = Req(' '.join(args))

    print "prefix:", prefix
    check_write()
    if opts.remove:                               #  --remove
        remove_req(req)
        return

    dists = get_dists(req,                        #  dists
                      'root' if opts.no_deps else 'recur')

    # Warn the user about packages which depend on what will be updated
    depend_warn([dist_naming.filename_dist(d) for d in dists])

    # Packages which are installed currently
    sys_inst = set(egginst.get_installed(sys.prefix))
    if prefix == sys.prefix:
        prefix_inst = sys_inst
    else:
        prefix_inst = set(egginst.get_installed(prefix))
    all_inst = sys_inst | prefix_inst

    # These are the packahes which are being excluded from being installed
    if opts.forceall:
        exclude = set()
    else:
        exclude = all_inst
        if opts.force:
            exclude.discard(dist_naming.filename_dist(dists[-1]))

    # Fetch distributions
    if not isdir(config.get('local')):
        os.makedirs(config.get('local'))
    for dist in iter_dists_excl(dists, exclude):
        c.fetch_dist(dist, config.get('local'),
                     check_md5=opts.force or opts.forceall,
                     dry_run=dry_run)

    # Remove packages (in reverse install order)
    for dist in dists[::-1]:
        fn = dist_naming.filename_dist(dist)
        if fn in all_inst:
            # if the distribution (which needs to be installed) is already
            # installed don't remove it
            continue
        cname = cname_fn(fn)
        # Only remove packages installed in prefix
        for fn_inst in prefix_inst:
            if cname == cname_fn(fn_inst):
                egginst_remove(fn_inst)

    # Install packages
    installed_something = False
    for dist in iter_dists_excl(dists, exclude):
        installed_something = True
        egginst_install(dist)

    if not installed_something:
        print "No update necessary, %s is up-to-date." % req
        print_installed_info(req.name)


if __name__ == '__main__':
    main()
