import sys

from encore.events.api import (ProgressStartEvent, ProgressStepEvent,
                               ProgressEndEvent)


def write_static(s):
    sys.stdout.write('\b%s%s' % (s, '\b'*len(s)))
    sys.stdout.flush()


class ProgressDisplay(object):
    """ Manage the display of progress indicators """

    def __init__(self, event_manager):
        self.event_manager = event_manager
        self.writers = {}
        self._format = '%s:\n'
        self.event_manager.connect(ProgressStartEvent, self.start_listener)

    def start_listener(self, event):
        # display initial text
        sys.stdout.write(self._format % event.message)
        sys.stdout.flush()

        # create a ProgressWriter instance
        writer = ProgressWriter(self, event.operation_id, event.steps)
        self.writers[event.operation_id] = writer

        # connect listeners
        self.event_manager.connect(ProgressStepEvent, writer.step_listener,
            filter={'operation_id': event.operation_id})
        self.event_manager.connect(ProgressEndEvent, writer.end_listener,
            filter={'operation_id': event.operation_id})


class ProgressWriter(object):
    """ Display an animated progress bar """

    def __init__(self, display, operation_id, steps):
        self.display = display
        self.operation_id = operation_id
        self.steps = steps
        self._max = 70
        self.last_step = 0
        self._format = '%5d [%'+str(-self._max)+'s]'

    def step_listener(self, event):
        stars = int(round(float(event.step)/self.steps*self._max))
        write_static(self._format % (event.step, '*'*(stars)))
        self.last_step = event.step

    def end_listener(self, event):
        if event.exit_state == 'normal':
            write_static(self._format % (self.last_step, '*'*self._max))
            sys.stdout.write('\nDone.\n')
            sys.stdout.flush()
        else:
            sys.stdout.write('\n%s: %s\n' % (event.exit_state.upper(),
                                             event.message))
            sys.stdout.flush()
        del self.display.writers[self.operation_id]
