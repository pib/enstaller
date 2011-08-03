import unittest
from os.path import dirname, join

import enstaller.history as history


history.PATH = join(dirname(__file__), 'history')


class TestHistory(unittest.TestCase):

    def test_find_revision(self):
        times = [
            '2011-08-01 21:17:22 CDT',
            '2011-08-01 22:38:37 CDT',
            '2011-08-01 23:05:07 CDT',
        ]
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
            self.assertEqual(history.find_revision(times, dt), res)

    def test_get_state(self):
        self.assertEqual(history.get_state(0),
                         set(['appinst-2.1.0-1.egg',
                              'basemap-1.0.1-1.egg',
                              'biopython-1.57-2.egg']))
        self.assertEqual(history.get_state(),
                         set(['basemap-1.0.2-1.egg',
                              'biopython-1.57-2.egg',
                              'numpy-1.7.0-1.egg']))


if __name__ == '__main__':
    unittest.main()
