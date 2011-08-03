import unittest
from datetime import datetime

from enstaller.parse_dt import parse



class TestParseDT(unittest.TestCase):

    def test_parse(self):
        ref = datetime(2011, 8, 2, 23, 3, 43)

        for s, res in [
            ('2011-08-01 21:17:21', '2011-08-01 21:17:21'),
            ('3 sec', '2011-08-02 23:03:40'),
            ('2 minutes', '2011-08-02 23:01:43'),
            ('4 hrs', '2011-08-02 19:03:43'),
            ('yesterday', '2011-08-01 23:03:43'),
            ('2 days', '2011-07-31 23:03:43'),
            ('1week', '2011-07-26 23:03:43'),
            ('3 weeks', '2011-07-12 23:03:43'),
            ]:
            self.assertEqual(parse(s, ref), res)


if __name__ == '__main__':
    unittest.main()
