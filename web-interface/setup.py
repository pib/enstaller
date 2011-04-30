from distutils.util import convert_path

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name="enpkg_server",
    version="1.0",
    author="Enthought, Inc.",
    author_email="info@enthought.com",
    url = "https://github.com/enthought/enstaller",
    license="BSD",
    description = "Install and managing tool for egg-based packages",
    packages = [
        'enpkg_server',
    ],
    entry_points = {
        "console_scripts": [
             "enpkg-server = enpkg_server.main:main",
        ],
    },
)
