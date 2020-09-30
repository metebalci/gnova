from __future__ import absolute_import, unicode_literals

import octoprint.plugin
import rtmidi
import time
import logging
import signal
import sys


def xy2note(x, y):
    return y * 10 + x


class GNovaController:

    def connect(self):
        self._logger.info('Connecting to Novation Launchpad...')
        mout = rtmidi.RtMidiOut()
        first = False
        second = None
        for i in range(0, mout.getPortCount()):
            portname = mout.getPortName(i)
            self._logger.info('Port: %s' % portname)
            if portname.startswith('Launchpad Mini MK3'):
                if first:
                    second = i
                    break
                else:
                    first = True
        if second:
            self._logger.info('Opening port: %s' % mout.getPortName(second))
            mout.openPort(second)
            self.mout = mout
            self._logger.info('Connected.')
            self.set_pmode(True)
            self.clear()
            self.noteon(1, 81, 5)
        else:
            raise Exception('Cannot connect to Novation Launchpad.')

    def disconnect(self):
        self.clear()
        self.cc(1, 91, 0)
        self.set_pmode(False)
        del self.mout
        self._logger.info('Disconnected from Novation Launchpad.')

    def show_line(self, y, arr):
        for x in range(1, 9):
            if arr[x-1]:
                self.noteon(1, xy2note(x, y), 1)
            time.sleep(0.01)
        for x in range(1, 9):
            self.noteon(1, xy2note(x, y), 0)

    def on_gcode(self, line, gcode):
        if line is None:
            return
        line = line.strip()
        # blank line ?
        if len(line) == 0:
            return
        # block delete
        elif line[0] == '/':
            return
        elif line[0] == '%':
            return
        # comment line ?
        elif line[0] == ';':
            return
        words = line.split()
        g0 = False
        g1 = False
        g2 = False
        g3 = False
        g92 = False
        x = False
        y = False
        z = False
        i = False
        e = False
        f = False
        s = False
        m21 = False
        m105 = False
        for idx in range(0, len(words)):
            word = words[idx]
            # inline comment
            if word.startswith(';'):
                break
            if word[0] == 'N':
                continue
            elif g0 or g1 or g92:
                if word.startswith('X'):
                    x = True
                elif word.startswith('Y'):
                    y = True
                elif word.startswith('Z'):
                    z = True
                elif word.startswith('I'):
                    i = True
                elif word.startswith('E'):
                    e = True
                elif word.startswith('F'):
                    f = True
                elif word.startswith('S'):
                    s = True
            elif word == 'M105':
                m105 = True
            elif word == 'M21':
                m21 = True
            elif word == 'G0':
                g0 = True
            elif word == 'G1':
                g1 = True
            elif word == 'G2':
                g2 = True
            elif word == 'G3':
                g3 = True
            elif word == 'G92':
                g92 = True
            else:
                pass
        if g0:
            arr = [g0, x, y, z, e, f, s, False]
            self.show_line(7, arr)
        elif g1:
            arr = [g1, x, y, z, e, f, s, False]
            self.show_line(6, arr)
        elif g2:
            arr = [g2, x, y, i, e, f, False, False]
            self.show_line(5, arr)
        elif g3:
            arr = [g3, x, y, i, e, f, False, False]
            self.show_line(4, arr)
        elif g92:
            arr = [g92, x, y, z, e, False, False, False]
            self.show_line(3, arr)
        elif m105:
            arr = [m105, False, False, False, False, False, False, False]
            self.show_line(1, arr)
        elif m21:
            arr = [False, m21, False, False, False, False, False, False]
            self.show_line(1, arr)
        else:
            self.blink_note(88, 41)

    def set_pmode(self, en):
        msg = rtmidi.MidiMessage.createSysExMessage(
            bytes([0x00, 0x20, 0x29, 0x02, 0x0D, 0x00, 0x7F if en else 0x05]))
        self.mout.sendMessage(msg)

    def noteon(self, channel, note, velocity):
        msg = rtmidi.MidiMessage.noteOn(channel, note, velocity)
        self.mout.sendMessage(msg)

    def cc(self, channel, controller_type, value):
        msg = rtmidi.MidiMessage.controllerEvent(channel, controller_type,
                                                 value)
        self.mout.sendMessage(msg)

    def blink_note(self,  note, value):
        self.noteon(1, note, value)
        time.sleep(0.01)
        self.noteon(1, note, 0)

    def blink_cc(self, controller_type, value):
        self.cc(1, controller_type, value)
        time.sleep(0.01)
        self.cc(1, controller_type, 0)

    def clear(self):
        for x in range(1, 9):
            for y in range(1, 9):
                self.noteon(1, xy2note(x, y), 0)
        for x in range(91, 100):
            self.cc(1, x, 0)
        for x in range(19, 99, 10):
            self.cc(1, x, 0)


class GNovaPlugin(octoprint.plugin.StartupPlugin,
                  octoprint.plugin.ShutdownPlugin,
                  octoprint.plugin.EventHandlerPlugin,
                  GNovaController):

    def on_startup(self, *args, **kwargs):
        self.connect()

    def on_shutdown(self, *args, **kwargs):
        self._logger.info('Disconnecting from Novation Launchpad')
        self.disconnect()

    def on_event(self, event, payload, *args, **kwargs):
        if event == 'PrinterStateChanged':
            if payload['state_string'] == 'Operational':
                self.noteon(1, 81, 13)
            elif payload['state_string'] == 'Printing':
                self.noteon(1, 81, 21)
            else:
                self.noteon(1, 81, 5)

    def gcode_sent(self, comm_instance, phase, cmd, cmd_type, gcode,
                   subcode, tags, *args, **kwargs):
        self.on_gcode(cmd, gcode)


__plugin_name__ = "gnova"
__plugin_version__ = "1.0.0"
__plugin_description__ = "G-Code Visualizer on Novation Launchpad Mini MK3"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = GNovaPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {'octoprint.comm.protocol.gcode.sent':
                        __plugin_implementation__.gcode_sent}


def signal_handler(sig, frame):
    global test_run
    test_run = False


if __name__ == "__main__":
    global test_run
    test_run = True
    signal.signal(signal.SIGINT, signal_handler)
    ctrl = GNovaController()
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    ctrl._logger = logging.getLogger()
    ctrl.connect()
    with open('test.gcode') as fp:
        while True and test_run:
            line = fp.readline()
            if line is None:
                break
            words = line.split()
            if len(words) > 0:
                ctrl.on_gcode(line, words[0])
    ctrl.disconnect()
