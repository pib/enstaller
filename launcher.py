import os
import subprocess
import urllib2
import zipfile
from optparse import OptionParser




def main():
    p = OptionParser(usage="usage: %prog [options] PYTHON_SCRIPT",
                     description=__doc__)

    p.add_option("--env",
                 action="store",
                 help="Python environment file(s), separated by ';'",
                 metavar='PATH')

    p.add_option('-v', "--verbose", action="store_true")
    p.add_option('--version', action="store_true")

    opts, args = p.parse_args()


if __name__ == '__main__':
    main()
