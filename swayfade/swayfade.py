from i3ipc import Connection, Event
from threading import Thread
from time import sleep
import argparse
from xdg import BaseDirectory
import os
import pathlib
import toml


class Fader:
    ipc = None

    def __init__(self, active_opacity, inactive_opacity, floating_opacity, fade_time, frame_time):
        self.active_opacity = active_opacity
        self.inactive_opacity = inactive_opacity
        self.floating_opacity = floating_opacity
        self.fade_time = fade_time
        self.frame_time = frame_time

        self.fader_running = False
        self.fade_queue = []
        self.fade_data = {}
        self.current_win = None
        self.new_win = None

    def start(self):
        if self.ipc is not None:
            raise Exception('Already started')

        self.ipc = Connection()
        self.ipc.on(Event.WINDOW_FOCUS, self.on_window_focus)
        self.ipc.on(Event.WINDOW_NEW, self.on_window_new)
        self.ipc.on(Event.WINDOW_FLOATING, self.on_window_floating)

        for win in self.ipc.get_tree():
            if win.focused:
                change_opacity(win, self.active_opacity)
                self.current_win = win
            else:
                change_opacity(win, self.inactive_opacity)

        self.ipc.main()

    def stop(self):
        if self.ipc is None:
            raise Exception('Not started')

        self.ipc.off(self.on_window_focus)
        self.ipc.off(self.on_window_new)
        self.ipc.off(self.on_window_floating)

        for win in self.ipc.get_tree():
            change_opacity(win, 1)

        self.ipc.main_quit()

    def enqueue_fade(self, win, start, target, duration):
        if win.id in self.fade_queue:
            f = self.fade_data[win.id]
            change = (self.frame_time / duration) * (target - f['opacity'])
            f['change'] = change
            f['target'] = target

        else:
            change_opacity(win, start)
            change = (self.frame_time / duration) * (target - start)
            fade_data = {'opacity': start,
                         'change': change,
                         'target': target,
                         'win': win}

            self.fade_queue.append(win.id)
            self.fade_data[win.id] = fade_data

    def start_fader(self):
        if not self.fader_running:
            self.fader_running = True
            Thread(target=self.fader).start()

    def fader(self):
        while self.fade_queue:
            for win_id in self.fade_queue.copy():
                f = self.fade_data[win_id]
                f['opacity'] += f['change']

                finished = False
                if f['change'] > 0:
                    if f['opacity'] >= f['target']:
                        finished = True
                elif f['opacity'] <= f['target']:
                    finished = True

                if finished:
                    change_opacity(f['win'], f['target'])
                    self.fade_queue.remove(win_id)
                    del self.fade_data[win_id]

                else:
                    change_opacity(f['win'], f['opacity'])

            sleep(self.frame_time)
        self.fader_running = False

    def on_window_new(self, ipc, event):
        if event.container.type == 'floating_con':
            change_opacity(event.container, self.floating_opacity)
        else:
            change_opacity(event.container, self.inactive_opacity)
        self.new_win = event.container.id

    def on_window_floating(self, ipc, event):
        if event.container.id == self.current_win.id:
            self.current_win = event.container

    def on_window_focus(self, ipc, event):
        if self.current_win.id == event.container.id:
            return

        if self.current_win.type == 'floating_con':
            trans = self.floating_opacity
        else:
            trans = self.inactive_opacity

        if event.container.id == self.new_win:
            change_opacity(self.current_win, trans)
            change_opacity(event.container, self.active_opacity)
        else:
            self.enqueue_fade(self.current_win, self.active_opacity, trans, self.fade_time)
            if event.container.type == 'floating_con':
                self.enqueue_fade(event.container, self.floating_opacity, self.active_opacity, self.fade_time)
            else:
                self.enqueue_fade(event.container, self.inactive_opacity, self.active_opacity, self.fade_time)
            self.start_fader()

        self.current_win = event.container
        self.new_win = None


def change_opacity(win, trans):
    win.command('opacity ' + str(trans))


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
            description=("Fades unfocussed windows, for sway and i3\n"
                "Can be configured with a config file by default at either:\n"
                " - $XDG_CONFIG_HOME/swayfade/swayfade.conf\n"
                " - $HOME/.config/swayfade/swayfade.toml"
            ))
    parser.add_argument('-a', '--active-opacity', metavar='OPACITY', type=float,
            default=None, help='The opacity of active windows, between 0 and 1 (default 1)')
    parser.add_argument('-i', '--inactive-opacity', metavar='OPACITY', type=float,
            default=None, help='The opacity of inactive windows, between 0 and 1 (default 0.9)')
    parser.add_argument('-f', '--floating-opacity', metavar='OPACITY', type=float,
            default=None, help='The opacity of floating, inactive windows, between 0 and 1 (default 0.9)')
    parser.add_argument('-t', '--fade-time', metavar='TIME', type=float,
            default=None, help='The time, in seconds, for a window fade to complete (default 0.2)')
    parser.add_argument('-r', '--frame-time', metavar='TIME', type=float,
            default=None, help='The inter-frame time, in seconds, during fades (default 0.01)')
    parser.add_argument('-c', '--config', metavar='PATH', type=str,
            default=None, help='swayfade config file path')
    args = parser.parse_args()

    # Parse configuration file
    if args.config is not None:
        config_path = pathlib.Path(args.config)
    else:
        config_path = pathlib.Path(os.path.join(BaseDirectory.xdg_config_home,
            'swayfade', 'swayfade.toml'))

    config = dict()
    if os.path.isfile(config_path):
        config = toml.load(config_path)
    else:
        if args.config is not None:
            raise ValueError('Invalid config path')

    if args.active_opacity is not None:
        active_opacity = args.active_opacity
    else:
        try:
            active_opacity = config['active_opacity']
        except KeyError:
            active_opacity = 1

    if args.inactive_opacity is not None:
        inactive_opacity = args.inactive_opacity
    else:
        try:
            inactive_opacity = config['inactive_opacity']
        except KeyError:
            inactive_opacity = 0.9

    if args.floating_opacity is not None:
        floating_opacity = args.floating_opacity
    else:
        try:
            floating_opacity = config['floating_opacity']
        except KeyError:
            floating_opacity = 0.9

    if args.fade_time is not None:
        fade_time = args.fade_time
    else:
        try:
            fade_time = config['fade_time']
        except KeyError:
            fade_time = 0.2

    if args.frame_time is not None:
        frame_time = args.frame_time
    else:
        try:
            frame_time = config['frame_time']
        except KeyError:
            frame_time = 0.01

    if active_opacity < 0 or active_opacity > 1:
        raise TypeError('active-opacity must be between 0 and 1')
    if inactive_opacity < 0 or inactive_opacity > 1:
        raise TypeError('inactive-opacity must be between 0 and 1')
    if floating_opacity < 0 or floating_opacity > 1:
        raise TypeError('float-opacity must be between 0 and 1')
    if fade_time < 0:
        raise TypeError('fade-time cannot be negative')
    if frame_time < 0:
        raise TypeError('frame-time cannot be negative')

    f = Fader(active_opacity, inactive_opacity, floating_opacity, fade_time,
            frame_time)
    f.start()
    f.stop()
