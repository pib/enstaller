import sys
import platform


if '64' in platform.architecture()[0]:
    arch = 'amd64'
    bits = 64
else:
    arch = 'x86'
    bits = 32


def _guess_plat():
    sys_map = {'linux2': 'rh5', 'darwin': 'osx',
               'sunos5': 'sol', 'win32': 'win'}
    try:
        return '%s-%d' % (sys_map[sys.platform], bits)
    except KeyError:
        return None


try:
    from custom_tools import platform as custom_plat
except ImportError:
    custom_plat = _guess_plat()


SUBDIR_MAP = {
    'win-64': 'Windows/amd64',
    'win-32': 'Windows/x86',
    'osx-64': 'MacOSX/amd64',
    'osx-32': 'MacOSX/x86',
    'rh3-64': 'RedHat/RH3_amd64',
    'rh3-32': 'RedHat/RH3_x86',
    'rh5-64': 'RedHat/RH5_amd64',
    'rh5-32': 'RedHat/RH5_x86',
    'sol-64': 'Solaris/Sol10_amd64',
    'sol-32': 'Solaris/Sol10_x86',
}

subdir = SUBDIR_MAP.get(custom_plat)
