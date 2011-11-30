import shutil
import os
from os.path import dirname, isfile, join
from unittest import TestCase

from enstaller.main import Enstaller
from enstaller import config
from enstaller.indexed_repo.chain import Chain


class EnstallerTestCase(TestCase):
    def setUp(self):
        self.base_cfg = join(dirname(__file__), 'config',
                             '.enstaller4rc')
        test_cfg = self.base_cfg + '.copy'
        shutil.copy(self.base_cfg, test_cfg)
        config.home_config_path = test_cfg
        config.clear_cache()

        self.enst = Enstaller(Chain())

    def tearDown(self):
        config.clear_auth()

    def test_enstaller_userpass_upgrade(self):
        """ Username and password should be taken out of .enstaller4rc
        and stored in a keyring.
        """
        config.get_auth()
        config_contents = open(config.home_config_path).read()
        return # XXX
        self.assertTrue('EPD_auth' not in config_contents)
        username, password = config.get_auth()
        self.assertEqual(username, 'foo')
        self.assertEqual(password, 'bar')

        config.clear_auth()
        config_contents = open(config.home_config_path).read()
        self.assertTrue('EPD_username' not in config_contents)
        self.assertEqual(config.get_auth(), (None, None))

    def test_enstaller_userpass_new_config(self):
        """ Username and password should be stored in a keyring for
        brand-new config files, too
        """
        config.home_config_path = self.base_cfg + '.new'
        if isfile(config.home_config_path):
            os.unlink(config.home_config_path)
        config.clear_cache()

        config.change_auth('foo', 'bar')
        config_contents = open(config.home_config_path).read()
        return # XXX
        self.assertTrue('EPD_auth' not in config_contents)
        self.assertEqual(config.get_auth(), ('foo', 'bar'))

        config.clear_auth()
        self.assertEqual(config.get_auth(), (None, None))
        config.change_auth('foo', 'bar')
        self.assertEqual(config.get_auth(), ('foo', 'bar'))

    def test_enstaller_userpass_no_keyring(self):
        """ When the keyring module isn't available, username and
        password should be stored in the old method
        """
        keyring = config.keyring
        config.keyring = None
        try:
            config.get_auth()
            config_contents = open(config.home_config_path).read()
            self.assertTrue("EPD_auth = 'Zm9vOmJhcg=='" in config_contents)

            config.change_auth('bar', 'foo')
            config_contents = open(config.home_config_path).read()
            self.assertTrue("EPD_auth = 'YmFyOmZvbw=='" in config_contents)

            config.clear_auth()
            config_contents = open(config.home_config_path).read()
            self.assertTrue("EPD_auth" not in config_contents)
            self.assertEqual(config.get_auth(), (None, None))

            config.change_auth('foo', 'bar')
            self.assertEqual(config.get_auth(), ('foo', 'bar'))
        finally:
            config.keyring = keyring

    def test_enstaller_userpass_no_keyring_new_config(self):
        """ Username and password should be stored properly in a new
        config file, even with no keyring module
        """
        config.home_config_path = self.base_cfg + '.new'
        if isfile(config.home_config_path):
            os.unlink(config.home_config_path)
        config.clear_cache()

        keyring = config.keyring
        config.keyring = None
        try:
            config.change_auth('foo', 'bar')
            config_contents = open(config.home_config_path).read()
            self.assertTrue("EPD_auth = 'Zm9vOmJhcg=='" in config_contents)
            self.assertEqual(config.get_auth(), ('foo', 'bar'))
        finally:
            config.keyring = keyring

