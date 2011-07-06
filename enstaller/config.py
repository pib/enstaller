# Copyright by Enthought, Inc.
# Author: Ilan Schnell <ischnell@enthought.com>

import re
import os
import sys
import platform
from os.path import isfile, join

from enstaller import __version__
from utils import PY_VER, abs_expanduser
import plat


config_fn = ".enstaller4rc"
home_config_path = abs_expanduser("~/" + config_fn)
system_config_path = join(sys.prefix, config_fn)

pypi_url = 'http://www.enthought.com/repo/pypi/eggs/'
info_url = 'http://www.enthought.com/epd/index-info.bz2'
upgrade_epd_url = 'http://www.enthought.com/epd/upgrade'

default = dict(
    info_url=info_url,
    prefix=sys.prefix,
    proxy=None,
    noapp=False,
    local=join(sys.prefix, 'LOCAL-REPO'),
    EPD_auth=None,
    EPD_userpass=None,
    IndexedRepos=[pypi_url + plat.subdir + '/'],
)


def get_path():
    """
    Return the absolute path to our config file.
    """
    if isfile(home_config_path):
        return home_config_path
    if isfile(system_config_path):
        return system_config_path
    return None


def input_auth():
    from getpass import getpass
    print """\
In order to access the EPD repository, please enter your
username and password, which you use to subscribe to EPD.
If you are not subscribed to EPD, just hit Return.
"""
    username = raw_input('Username: ').strip()
    if not username:
        return None
    for dummy in xrange(3):
        password = getpass('Password: ')
        password2 = getpass('Confirm password: ')
        if password == password2:
            userpass = username + ':' + password
            return userpass.encode('base64').strip()
    return None

RC_TMPL = """\
# enstaller configuration file
# ============================
#
# This file contains the default package repositories, and configuration,
# used by enstaller %(version)s for the Python %(py_ver)s environment:
#
#   sys.prefix = %(sys_prefix)r
#
# This file was created by initially running the enpkg command.

%(auth_section)s
# The enpkg command is searching for eggs in the list 'IndexedRepos'.
# When enpkg is searching for an egg, it tries to find it in the order
# of this list, and selects the first one that matches, ignoring
# repositories below.  Therefore the order of this list matters.
#
# Placeholders '{ARCH}' get substituted by 'amd64' or 'x86', depending
# on the architecture of the current interpreter.
#
# Notice also that only indexed repositories, i.e. HTTP directories which
# contain a file 'index-depend.bz2' (next to the eggs), can be listed here.
# For local repositories, the index file is optional.  Remember that on
# Windows systems the backslaches in the directory path need to escaped, e.g.:
# r'file://C:\\repository\\' or 'file://C:\\\\repository\\\\'
IndexedRepos = [
%(repo_section)s]

# The following variable is optional and, if provided, point to a URL which
# contains an index file with additional package information, such as the
# package home-page, license type, description.  The information is displayed
# by the --info option.
#info_url = 'http://www.enthought.com/epd/index-info.bz2'

# Install prefix (enpkg --prefix and --sys-prefix options overwrite this).
# When this variable is not provided, it will default to the value of
# sys.prefix (within the current interpreter running enpkg)
#prefix = %(sys_prefix)r

# When running enpkg behind a firewall it might be necessary to use a proxy
# to access the repositories.  The URL for the proxy can be set here.
# Note that the enpkg --proxy option will overwrite this setting.
%(proxy_line)s

# Uncommenting the next line will disable application menu item install.
# This only effects the few packages which install menu items,
# which as IPython.
#noapp = True
"""

def write(proxy=None):
    """
    write the config file
    """
    try:
        from custom_tools import repo_section
    except ImportError:
        repo_section = ''

    # If user is 'root', then always create the config file in sys.prefix,
    # otherwise in the user's HOME directory.
    if sys.platform != 'win32' and os.getuid() == 0:
        path = system_config_path
    else:
        path = home_config_path

    auth = input_auth()
    if auth:
        auth_section = """
# The EPD subscriber authentication is required to access the EPD repository.
# To change this setting, use the 'enpkg --userpass' command which will ask
# you for your username and password.
EPD_auth = %r
""" % auth
    else:
        auth_section = ''

    py_ver = PY_VER
    sys_prefix = sys.prefix
    version = __version__

    if proxy:
        proxy_line = 'proxy = %r' % proxy
    else:
        proxy_line = '#proxy = <proxy string>  # e.g. "123.0.1.2:8080"'

    fo = open(path, 'w')
    fo.write(RC_TMPL % locals())
    fo.close()
    print "Wrote configuration file:", path
    print 77 * '='
    clear_cache()


def change_auth():
    path = get_path()
    if path is None:
        write()
        return
    fi = open(path)
    data = fi.read()
    fi.close()
    auth = input_auth()
    if not auth:
        return
    pat = re.compile(r'^EPD_auth\s*=.*$', re.M)
    authline = 'EPD_auth = %r' % auth
    if pat.search(data):
        data = pat.sub(authline, data)
    else:
        lines = data.splitlines()
        lines.insert(10, authline)
        data = '\n'.join(lines) + '\n'
    fo = open(path, 'w')
    fo.write(data)
    fo.close()


def prepend_url(url):
    f = open(get_path(), 'r+')
    data = f.read()
    pat = re.compile(r'^IndexedRepos\s*=\s*\[\s*$', re.M)
    if not pat.search(data):
        sys.exit("Error: IndexedRepos section not found")
    data = pat.sub(r"IndexedRepos = [\n  '%s'," % url, data)
    f.seek(0)
    f.write(data)
    f.close()


def arch_filled_url(url):
    from indexed_repo.dist_naming import cleanup_reponame

    return cleanup_reponame(url.replace('{ARCH}', plat.arch))


def clear_cache():
    if hasattr(read, 'cache'):
        del read.cache


def read():
    """
    return the configuration from the config file as a dictionary,
    and fix some values and give defaults
    """
    if hasattr(read, 'cache'):
        return read.cache

    path = get_path()
    read.cache = dict(default)
    if path is None:
        return read()

    d = {}
    execfile(path, d)
    for k in default.iterkeys():
        if not d.has_key(k):
            continue
        v = d[k]
        if k == 'IndexedRepos':
            read.cache[k] = [arch_filled_url(url) for url in v]
        elif k in ('prefix', 'local'):
            read.cache[k] = abs_expanduser(v)
        else:
            read.cache[k] = v
    return read()


def get(key):
    return read()[key]


def print_config():
    print "Python version:", PY_VER
    print "enstaller version:", __version__
    print "sys.prefix:", sys.prefix
    print "platform:", platform.platform()
    print "architecture:", platform.architecture()[0]
    print "config file:", get_path()
    print
    print "settings:"
    for k in 'info_url', 'prefix', 'local', 'noapp', 'proxy':
        print "    %s = %r" % (k, get(k))
    print "    IndexedRepos:"
    for repo in get('IndexedRepos'):
        print '        %r' % repo


if __name__ == '__main__':
    write()
    print_config()
