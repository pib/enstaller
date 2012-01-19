import sys


class ProgressManager(object):

    def __init__(self, event_manager, source, operation_id, steps,
                 message, filename, dispamount):
        self.action = message
        self.filename = filename
        self.dispamount = dispamount
        self._tot = steps
        self._cur = 0

    def __enter__(self):
        sys.stdout.write("%-56s %20s\n" % (self.filename,
                                           '[%s]' % self.action))
        sys.stdout.write('%9s [' % self.dispamount)
        sys.stdout.flush()

    def __call__(self, step=0):
        if 0 < step < self._tot and 64.0 * step / self._tot > self._cur:
            sys.stdout.write('.')
            sys.stdout.flush()
            self._cur += 1

    def __exit__(self, exc_type, exc_value, exc_traceback):
        sys.stdout.write('.' * (65 - self._cur))
        sys.stdout.write(']\n')
        sys.stdout.flush()
