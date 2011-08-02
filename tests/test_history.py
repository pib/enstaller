import unittest
from os.path import dirname, join

import enstaller.history as history


history.PATH = join(dirname(__file__), 'history')


class TestDistNaming(unittest.TestCase):

    def test_get_state(self):
        for dt, res in [
            ('2011-08-01 21:17:21 CDT', 0),
            ('2011-08-01 21:17:22 CDT', 0),
            ('2011-08-01 21:17:23 CDT', 0),
            ('2011-08-01 22:38:36 CDT', 0),
            ('2011-08-01 22:38:37 CDT', 1),
            ('2011-08-01 22:38:38 CDT', 1),
            ('2011-08-01 23:05:06 CDT', 1),
            ('2011-08-01 23:05:07 CDT', 2),
            ('2011-08-01 23:05:08 CDT', 2),
            ]:
            self.assertEqual(history.get_state(dt), res)


if __name__ == '__main__':
    unittest.main()
