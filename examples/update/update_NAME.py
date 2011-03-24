import sys
from os.path import join
from subprocess import check_call

from egginst.utils import bin_dir_name
from enstaller.indexed_repo import Chain, dist_naming
from enstaller.main import get_installed_info
from enstaller import config


config.get_path = lambda: config.SYSTEM_CONFIG_PATH


name = '@NAME@'
enpkg_bin = join(sys.prefix, bin_dir_name, 'enpkg')


def welcome():
    print """\
************************************************************************
*              Welcome to the %s update program. %s    *
************************************************************************
""" % (name, ' ' * (20-len(name)))

def quit():
    raw_input("Hit enter to quit> ")
    sys.exit()

def get_info():
    res = get_installed_info(sys.prefix, name)
    if res is None:
        print "Error: %r does not appear to be installed" % name
        quit()
    return res

def main():
    welcome()
    info = get_info()
    curr_ver = dist_naming.split_eggname(info['egg_name'])[1]
    print "Currently installed version:  %s" % curr_ver
    print "               installed on:  %s" % info['mtime']
    print

    conf = config.read()
    c = Chain(conf['IndexedRepos'])
    versions = c.list_versions(name)
    if len(versions) == 0:
        print "Error: no versions of %r available" % name
        quit()

    while True:
        print "Available versions:"
        print ', '.join(versions)
        print """
You have the following options:
  - press return to update to the latest available version %s
  - enter the version to update (or downgrade) to, e.g. %r
  - enter 'q' to quit (without changing anything)
""" % (versions[-1], versions[0])
        inp = raw_input('> ').strip()
        if inp.lower() in ('q', 'quit'):
            sys.exit()

        update_to = inp or versions[-1]
        if update_to in versions:
            print "Updating to: %s" % update_to
            check_call([enpkg_bin, '--sys-config', name, update_to])
            quit()
        print "You have entered %r, which is not an available version" % inp


if __name__ == '__main__':
    main()
