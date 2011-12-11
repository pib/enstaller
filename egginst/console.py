import sys
import logging


class ConsoleProgressHandler(logging.Handler):

    def emit(self, record):
        if record.name == 'progress.start':
            d = record.msg
            self._tot = d['amount']
            self._cur = 0
            sys.stdout.write("%-56s %20s\n" % (d['filename'],
                                               '[%s]' % d['action']))
            sys.stdout.write('%9s [' % d['disp_amount'])
            sys.stdout.flush()

        elif record.name == 'progress.update':
            n = record.msg
            if 0 < n < self._tot and float(n) / self._tot * 64 > self._cur:
                sys.stdout.write('.')
                sys.stdout.flush()
                self._cur += 1

        elif record.name == 'progress.stop':
            sys.stdout.write('.' * (65 - self._cur))
            sys.stdout.write(']\n')
            sys.stdout.flush()


def setup_handlers():
    prog_logger = logging.getLogger('progress')
    prog_logger.setLevel(logging.INFO)
    prog_logger.addHandler(ConsoleProgressHandler())
