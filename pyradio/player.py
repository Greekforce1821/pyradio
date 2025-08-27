# -*- coding: utf-8 -*-
import subprocess
import threading
import os
import random
import math
import logging
from os.path import expanduser
from platform import uname as platform_uname
from sys import platform
from time import sleep
from datetime import datetime
import collections
import json
import socket
from shutil import copyfile as shutil_copy_file
import locale
locale.setlocale(locale.LC_ALL, "")
# this is for windows...
try:
    from .common import STATES, M_STRINGS, Station
except ImportError:
    pass
try:
    import psutil
except:
    pass
if platform.startswith('win'):
    import win32pipe
    import win32file
    import pywintypes
try:
    from urllib import unquote
except:
    from urllib.parse import unquote

''' In case of import from win.py '''
try:
    from .cjkwrap import wrap
except:
    pass
''' In case of import from win.py '''
try:
    from .encodings import get_encodings
except:
    pass

logger = logging.getLogger(__name__)

available_players = []

try:  # Forced testing
    from shutil import which
    def pywhich (cmd):
        pr = which(cmd)
        if pr:
            return pr
        else:
            return None
except:
    # Versions prior to Python 3.3 don't have shutil.which

    def pywhich (cmd, mode=os.F_OK | os.X_OK, path=None):
        ''' Given a command, mode, and a PATH string, return the path which
            conforms to the given mode on the PATH, or None if there is no such
            file.
            `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
            of os.environ.get("PATH"), or can be overridden with a custom search
            path.
            Note: This function was backported from the Python 3 source code.
        '''
        # Check that a given file can be accessed with the correct mode.
        # Additionally check that `file` is not a directory, as on Windows
        # directories pass the os.access check.

        def _access_check(fn, mode):
            return os.path.exists(fn) and os.access(fn, mode) and not os.path.isdir(fn)

        # If we're given a path with a directory part, look it up directly
        # rather than referring to PATH directories. This includes checking
        # relative to the current directory, e.g. ./script
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd

            return None

        if path is None:
            path = os.environ.get('PATH', os.defpath)
        if not path:
            return None

        path = path.split(os.pathsep)

        if platform.startswith('win'):
            # The current directory takes precedence on Windows.
            if os.curdir not in path:
                path.insert(0, os.curdir)

            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get('PATHEXT', '').split(os.pathsep)
            # See if the given file matches any of the expected path
            # extensions. This will allow us to short circuit when given
            # "python.exe". If it does match, only test that one, otherwise we
            # have to try others.
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            # On other platforms you don't have things like PATHEXT to tell you
            # what file suffixes are executable, so just pass on cmd as-is.
            files = [cmd]

        seen = set()
        for dir in path:
            normdir = os.path.normcase(dir)
            if normdir not in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        return name

        return None

def find_vlc_on_windows(config_dir=None):
    PLAYER_CMD = ''
    for path in (
        os.path.join(os.getenv('PROGRAMFILES'), 'VideoLAN', 'VLC', 'vlc.exe'),
        os.path.join(os.getenv('PROGRAMFILES') + ' (x86)', 'VideoLAN', 'VLC', 'vlc.exe'),
    ):
        if os.path.exists(path):
            PLAYER_CMD = path
            break
    return PLAYER_CMD

    #result = []
    #for root, dirs, files in os.walk(path):
    #    for name in files:
    #        if fnmatch.fnmatch(name, pattern):
    #            result.append(os.path.join(root, name))
    #return result

def find_mpv_on_windows():
    for a_path in (
        os.path.join(os.getenv('APPDATA'), 'pyradio', 'mpv', 'mpv.exe'),
        os.path.join(os.getenv('APPDATA'), 'mpv', 'mpv.exe'),
        os.path.join(expanduser("~"), 'mpv', 'mpv.exe')
    ):
        if os.path.exists(a_path):
            return a_path
    return 'mpv'

def find_mplayer_on_windows():
    for a_path in (
        os.path.join(os.getenv('APPDATA'), 'pyradio', 'mplayer', 'mplayer.exe'),
        os.path.join(os.getenv('APPDATA'), 'mplayer', 'mplayer.exe'),
        os.path.join(expanduser("~"), 'mplayer', 'mplayer.exe')
    ):
        if os.path.exists(a_path):
            return a_path
    return 'mplayer'

def info_dict_to_list1(info, fix_highlight, max_width):
    # logger.error(f'\n\ninfo_dict_to_list max_width = {max_width}\n\n')
    result_dict = {}
    max_label_length = max(len(label) for label in info.keys())
    label_padding = 2  # for ": " separator
    label_width = max_label_length + label_padding

    for label, text in info.items():

        if label == 'text':
            # Wrap the text using cjkwrap.wrap
            wrapped_lines = wrap(text, width=max_width)
        else:

            # Right-align the label
            formatted_label = f"{label:>{label_width}}:"
            # formatted_label = label.rjust(label_width, '_')

            # Wrap the text using cjkwrap.wrap
            wrapped_lines = wrap(text, width=max_width - label_width)
            # logger.error(f'\n\n\n"{text}"\n\n{wrapped_lines}\n============')

            # Store the result in the dictionary
        result_dict[label] = wrapped_lines

    out = []
    for label, wrapped_lines in result_dict.items():
        # logger.error('wrapped_lines\n{}'.format(wrapped_lines))
        if label != 'text':
            if wrapped_lines:
                formatted_label = f"{label:_>{label_width-2}}"
                if out:
                    out.append((f"{formatted_label:>{label_width-2}}: |{wrapped_lines[0]}"))
                else:
                    out.append((f"{formatted_label:>{label_width-2}}: {wrapped_lines[0]}"))
                for i in range(1, len(wrapped_lines)):
                    out.append('_' * label_width + '|' + wrapped_lines[i])
    if 'text' in result_dict:
        out.append('')
        for n in result_dict['text']:
            out.append(n)
    #logger.info('out\n{}\n\n'.format(out))
    return out

def info_dict_to_list(info, fix_highlight, max_width, win_width):
    max_len = 0
    for a_title in info.keys():
        if len(a_title) > max_len:
            max_len = len(a_title)
        info[a_title] = info[a_title].replace('_','¸')
    # logger.error('DE info\n{}\n\n'.format(info))

    # logger.info(f'{max_width = }, {win_width = }')
    # logger.error(f'{info = }')
    max_str = max([len(item[0]) + len(item[1]) + 2 for item in info.items()])
    # # logger.error(f'{max_str = }')
    # # max_str = max([len(l[1]) + 2 for l in info.items()])
    # logger.info(f'{max_str = }, {max_width = }, {win_width = }')
    if win_width - 24 >= max_str:
        max_width = max_str + 3
    # logger.error(f'{max_width = }')
    a_list = []
    for n in info.keys():
        a_list.extend(wrap(n.rjust(max_len, ' ') + ': |' + info[n],
                             width=max_width,
                             subsequent_indent=(2+max_len)*'_'))

    # logger.error('DE a_list\n\n{}\n\n'.format(a_list))

    ''' make sure title is not alone in line '''
    for a_title in ('URL:', 'site:', 'Genre:'):
        for n, an_item in enumerate(a_list):
            if an_item.endswith(a_title):
                url = a_list[n+1].split('_|')[1]
                # merge items
                bar = '' if a_title.endswith('L:') else '|'
                a_list[n] = a_list[n] + ' ' + bar + url
                a_list.pop(n+1)
                break

    # logger.error('DE a_list\n\n{}\n\n'.format(a_list))

    a_list[0] = a_list[0].replace('|', '')

    if fix_highlight:
        rep_name = 0
        web_name = 0
        for x in fix_highlight:
            for n, an_item in enumerate(a_list):
                if x[0] in an_item:
                    rep_name = n
                if x[1] in an_item:
                    web_name = n
                    break
            for n in range(rep_name + 1, web_name):
                a_list[n] = '|' + a_list[n]
    # logger.error('DE a_list\n\n{}\n\n'.format(a_list))
    return a_list

class Player():
    ''' Media player class. Playing is handled by player sub classes '''
    process = None
    update_thread = None

    buffering = False

    icy_title_prefix = 'Title: '
    title_prefix = ''

    # Input:   old user input     - used to early suppress output
    #                               in case of consecutive equal messages
    # Volume:  old volume input   - used to suppress output (and firing of delay thread)
    #                               in case of consecutive equal volume messages
    # Title:   old title input    - printed by delay thread
    oldUserInput = {'Input': '', 'Volume': '', 'Title': ''}

    delay_thread = None
    connection_timeout_thread = None

    ''' make it possible to change volume but not show it '''
    show_volume = True

    muted = paused = False

    ctrl_c_pressed = False

    ''' When found in station transmission, playback is on
     '''
    _playback_token_tuple = (
            'AO: [',                    # for mplayer
            'CACHE_PRE_INIT',           # for mplayer using cache
            '(+) Audio '                # for mpv python 2
            )
    # _playback_token_tuple = ( 'AO: [', 'Cache size')

    icy_tokens = ()
    icy_audio_tokens = {}

    playback_is_on = connecting = False

    _station_encoding = 'utf-8'

    # used to stop mpv update thread on python3
    stop_mpv_status_update_thread = False

    # used to stop vlc update thread on windows
    stop_win_vlc_status_update_thread = False

    # bitrate, url, audio_format etc.
    _icy_data = {}

    GET_TITLE = b'{ "command": ["get_property", "metadata"], "request_id": 100 }\n'
    GET_AUDIO_FORMAT = b'{ "command": ["get_property", "audio-out-params"], "request_id": 200 }\n'
    GET_AUDIO_CODEC = b'{ "command": ["get_property", "audio-codec"], "request_id": 300 }\n'
    GET_AUDIO_CODEC_NAME = b'{ "command": ["get_property", "audio-codec-name"], "request_id": 400 }\n'
    GET_ERROR = b'{"command": ["get_property", "user-data/mpv/ytdl/json-subprocess-result"], "request_id": 700 }\n'

    all_config_files = {}

    NO_RECORDING = 0
    RECORD_AND_LISTEN = 1
    RECORD_WITH_SILENCE = 2
    _recording = 0
    _recording_from_schedule = 0
    recording_filename = ''

    name = ''

    _chapters = None

    currently_recording = False

    success_in_check_playlist = None
    error_in_check_playlist = None

    enable_per_station_volume = True

    def __init__(self,
                 config,
                 outputStream,
                 playback_timeout_counter,
                 playback_timeout_handler,
                 info_display_handler,
                 history_add_function,
                 recording_lock):
        self.PROFILE_FROM_USER = False
        self.volume = -1
        self.station_volume = -1
        self._chapter_time = None
        self.stop_timeout_counter_thread = False
        self._request_mpv_info_data_counter = 0
        self.detect_if_player_exited = False
        self.outputStream = outputStream
        self._cnf = config
        self.stations_history_add_function = history_add_function
        self.config_encoding = self._cnf.default_encoding
        self.config_dir = self._cnf.stations_dir
        try:
            self.playback_timeout = int(self._cnf.connection_timeout_int)
        except ValueError:
            self.playback_timeout = 10
        self.force_http = self._cnf.force_http
        self.playback_timeout_counter = playback_timeout_counter
        self.playback_timeout_handler = playback_timeout_handler
        self.info_display_handler = info_display_handler
        self.status_update_lock = outputStream.lock

        self.config_files = []
        self.all_config_files = self._cnf.profile_manager.config_files
        self._cnf.profile_manager.set_vlc_config_file([os.path.join(self._cnf.state_dir, 'vlc.conf')])
        # TODO: get profile names?
        # self._cnf.profile_manager.
        #if self.WIN and self.PLAYER_NAME == 'vlc':
        if platform.startswith('win'):
            ''' delete old vlc files (vlc_log.*) '''
            from .del_vlc_log import RemoveWinVlcLogFiles
            threading.Thread(target=RemoveWinVlcLogFiles(self.config_dir)).start()

        ''' Recording monitor player for MPlayer and VLC '''
        self.monitor = self.monitor_process = None
        self.monitor_opts = self.monitor_update_thread = None
        self._recording_lock = recording_lock
        self.already_playing = False

        ''' I True, we have mplayer on Windows
            ehich will not support profiles
        '''
        self._mplayer_on_windows7 = False

        # per station buffering
        self._buffering_data = None

    def _return_false(self):
        return False

    @property
    def profile_name(self):
        if self.PLAYER_NAME == 'vlc':
            return ''
        # logger.error('***** self.params\n{}'.format(self.params))
        candidate = self.params[self.params[0]]
        # logger.error('candidate = "{}"'.format(candidate))
        if candidate:
            if candidate.startswith('profile:'):
                candidate = candidate.replace('profile:', '')
                # logger.error('candidate = "{}"'.format(candidate))
                return candidate
        return 'pyradio'

    @profile_name.setter
    def profile_name(self, val):
        raise ValueError('parameter is read only')

    @property
    def profile_token(self):
        return  '[' + self.profile_name + ']'

    @profile_token.setter
    def profile_token(self, value):
        raise ValueError('property is read only')

    @property
    def recording(self):
        if self._recording_from_schedule > 0:
            return self._recording_from_schedule
        else:
            return self._recording

    @recording.setter
    def recording(self, val):
        if val in range(0, 3):
            self._recording = val
        else:
            self._recording = 0
        logger.error(f'\n\nsetting recording to {self._recording}')

    @property
    def buffering_data(self):
        return self._buffering_data

    @buffering_data.setter
    def buffering_data(self, val):
        self._buffering_data = val

    def write_chapters(self):
        ''' write chapters from a player crash reoutine '''
        if self._chapters and self.recording:
            self._chapters.write_chapters_to_file(self.recording_filename)

    def _player_is_buffering(self, opts, tokens):
        # logger.error('opts = {}'.format(opts))
        # logger.error('tokens = {}'.format(tokens))
        for k in tokens:
            for n in opts:
                if k in n:
                    return True
        return False

    def _configHasProfile(self, a_profile_name=None):
        ''' Checks if a player config files have
            a_profile_name profile entry (default: pyradio).

            On Windows 7 it disables the use of profiles.

            Returns:
                USE_PROFILE
                    -1: Do not use profiles
                     0: Do not use profiles
                     1: Use profile
                profile_name
                    The name of the profile to use
        '''
        self.PROFILE_FROM_USER = False
        if self.PLAYER_NAME == 'mplayer' and \
                self._mplayer_on_windows7:
            if logger.isEnabledFor(logging.INFO):
                logger.info('>>>>> Disabling profiles usage on Windows 7 <<<<<')
            return -1, None
        if a_profile_name is None:
            a_profile_token = self.profile_token
        else:
            a_profile_token = '[' + a_profile_name + ']'
        self.PROFILE_FROM_USER = False
        for config_file in self.config_files:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_string = f.read()
                if a_profile_token in config_string:
                    self.PROFILE_FROM_USER = True
                    return 1, a_profile_name

        ''' profile not found in config
            create a default profile
        '''
        ret = self._cnf.profile_manager.add_to_config(
            self.PLAYER_NAME, 'pyradio', self.NEW_PROFILE_STRING
        )
        if ret is None:
            return 0, a_profile_name
        return 1, a_profile_name

    def get_recording_filename(self, name, extension):
        if self._chapters is None:
            self._chapters = PyRadioChapters(
                    self._cnf,
                    chapter_time=lambda: self._chapter_time
                    )
        else:
            self._chapters.look_for_mkvmerge()
        f = datetime.now().strftime('%Y-%m-%d %H-%M-%S') + " " + name  + extension
        if self._chapters.HAS_MKVTOOLNIX:
            return os.path.join(self._cnf.recording_dir, 'tmp_' + f)
        else:
            return os.path.join(self._cnf.recording_dir, f)

    def _get_all_config_files(self):
        ''' MPV config files '''
        if platform.startswith('win'):
            config_files = [os.path.join(os.getenv('APPDATA'), "mpv", "mpv.conf")]
        else:
            # linux, freebsd, etc.
            xdg_config = os.getenv('XDG_CONFIG_HOME')
            if xdg_config:
                config_files = [xdg_config + "/mpv/mpv.conf"]
            else:
                config_files = [expanduser("~") + "/.config/mpv/mpv.conf"]
            config_files.append("/etc/mpv/mpv.conf")
            config_files.append("/usr/local/etc/mpv/mpv.conf")
        self.all_config_files['mpv'] = config_files[:]

        ''' MPlayer config files '''
        config_files = [expanduser("~") + "/.mplayer/config"]
        if platform.startswith('win'):
            if os.path.exists(r'C:\\mplayer\\mplayer.exe'):
                config_files[0] = r'C:\\mplayer\mplayer\\config'
            elif os.path.exists(os.path.join(os.getenv('USERPROFILE'), "mplayer", "mplayer.exe")):
                config_files[0] = os.path.join(os.getenv('USERPROFILE'), "mplayer", "mplayer", "config")
            elif os.path.exists(os.path.join(os.getenv('APPDATA'), "pyradio", "mplayer", "mplayer.exe")):
                config_files[0] = os.path.join(os.getenv('APPDATA'), "pyradio", "mplayer", "mplayer", "config")
            else:
                config_files = []
        else:
            config_files.append("/usr/local/etc/mplayer/mplayer.conf")
            config_files.append('/etc/mplayer/config')
        self.all_config_files['mplayer'] = config_files[:]

        '''' VLC config file '''
        config_files = [os.path.join(self._cnf.state_dir, 'vlc.conf')]
        self.all_config_files['vlc'] = config_files[:]
        self._restore_win_player_config_file()
        if not os.path.exists(self.all_config_files['vlc'][0]):
            ''' create a default vlc config file '''
            try:
                with open(self.all_config_files['vlc'][0], 'w', encoding='utf-8') as f:
                    f.write('50')
            except:
                pass

    def __del__(self):
        self.close()

    def _can_update_br(self, a_br):
        if a_br and a_br != '128':
            if [x for x in self._cnf.AVAILABLE_PLAYERS if x.PLAYER_NAME == 'mplayer']:
                return True
        return False

    def _url_to_use(self, streamUrl, station_force_http):
        if self.force_http or station_force_http:
            return streamUrl.replace('https://', 'http://')
        else:
            return streamUrl

    def _on_connect(self):
        logger.error('empty on_connect')
        pass

    def set_volume(self, vol):
        if self.isPlaying() and \
                not self.muted:
            executed = []
            wanted = '010'
            self.get_volume()
            while vol != int(self.volume):
                old_vol = int(self.volume)
                if vol > int(self.volume):
                    self._volume_up()
                    executed.append(0)
                else:
                    self._volume_down()
                    executed.append(1)
                if wanted in ''.join(map(str, executed)):
                    break
                if self.PLAYER_NAME == 'mpv':
                    sleep(.01)
                while old_vol == int(self.volume):
                    sleep(.1)

    def create_monitor_player(self, stop, limit, notify_function):
        # logger.info('\n\n======|||==========')
        # self.monitor_opts.append('--volume')
        # self.monitor_opts.append('300')
        # logger.info(self.monitor_opts)
        # logger.error('limit = {}'.format(limit))
        while not os.path.exists(self.recording_filename):
            sleep(.1)
            if stop():
                logger.error('Asked to stop. Exiting....')
                return
        # logger.error('while 2')
        while os.path.getsize(self.recording_filename) < limit:
            sleep(.1)
            if stop():
                # logger.error('\n\nAsked to stop. Exiting....\n\n')
                return
        if stop():
            # logger.error('\n\nAsked to stop. Exiting....\n\n')
            return
        # logger.error('----------------------starting!')
        self.monitor_process = subprocess.Popen(
            self.monitor_opts, shell=False,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        # logger.error('self.monitor_process.pid = {}'.format(self.monitor_process))
        # logger.error('------------------ to notify function')
        notify_function()
        # logger.error('------------------ after notify function')
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'----==== {self.PLAYER_NAME} monitor started ====----\nExecuting command {self.monitor_opts}')

    def save_volume(self):
        pass

    def icy_data(self, a_member):
        ret = ''
        with self.status_update_lock:
            if self._icy_data:
                if a_member in self._icy_data:
                    ret = self._icy_data[a_member]
        return ret

    def icy_data_available(self):
        with self.status_update_lock:
            length = len(self._icy_data)
        if length == 0:
            return False
        return True

    def get_info_string(self, a_station, max_width, win_width):
        guide = (
            ('Reported Name',  'icy-name'),
            ('Website', 'icy-url'),
            ('Genre', 'icy-genre'),
            ('Bitrate', 'icy-br'),
            ('Audio', 'audio_format'),
            ('Codec Name', 'codec-name'),
            ('Codec', 'codec')
        )

        enc = get_encodings()
        if self._station_encoding == '':
            this_enc = self._config_encoding
        else:
            this_enc = self._station_encoding
        try:
            this_enc_string = [x for x in enc if x[0] == this_enc][0][2]
        except:
            this_enc_string = 'Unknown'
        enc_to_show = f'{this_enc} ({this_enc_string})'


        info = collections.OrderedDict()
        info['Playlist Name'] = a_station[0]
        for x in guide:
            if x[1] in self._icy_data:
                info[x[0]] = self._icy_data[x[1]].strip()
            else:
                info[x[0]] = ''
            if x[0] == 'Bitrate':
                if info[x[0]]:
                    info[x[0]] += ' kb/s'
            if x[0] == 'Genre':
                info['Encoding'] = enc_to_show
            if x[0].startswith('Reported'):
                info['Station URL'] = a_station[1].strip()
        info['Website'] = unquote(info['Website']).strip()


        logger.error(f'{info = }')

        a_list = []
        fix_highlight = (
                ('Reported ', 'Station URL:'),
                ('Website:', 'Genre:'),
                ('Genre:', 'Encoding:')
                )
        # logger.error('\n\n**** win_width = {}\n\n'.format(win_width))
        a_list = info_dict_to_list(info, fix_highlight, max_width, win_width)

        # for n in a_list:
        #     logger.debug(f'{n}')
        # logger.debug('\n\n\n')

        if 'Codec:' not in a_list[-1]:
            a_list.append('        Codec:')

        # if a_list[1].startswith('_'):
        #     a_list[1] = '|' + a_list[1]
        # logger.error(f'a_list[1] = {a_list[1]}')
        # if a_list[1].startswith('||'):
        #     a_list[1] == a_list[1][1:]
        # logger.error(f'a_list[1] = {a_list[1]}')

        ret = '|' + '\n'.join(a_list).replace('Encoding: |', 'Encoding: ').replace('URL: |', 'URL: ').replace('\n', '\n|')
        tail = ''
        if 'icy-name' in self._icy_data:
            if self._cnf._online_browser is None and \
            (
                a_station[0] != self._icy_data['icy-name'] and \
                self._icy_data['icy-name'] and \
                self._icy_data['icy-name'] != '(null)'
            ):
                tail = '\n\nPress |r| to rename the station to the |Reported Name|, or'
        return ret + '\n\n|Highlighted values| are user specified.\nOther values are station provided (live) data.', tail

    def _do_save_volume(self, config_string):
        # logger.error('\n\nself.volume = {}\n\n'.format(self.volume))
        if not self.config_files:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('Volume not saved!!! (config file not found!!!)')
            return 'Volume not saved!!!'
        ret_strings = ('Volume: no initial value set...',
                       'Volume: {}% saved',
                       'Volume: {}% NOT saved (Error writing file)',
                       'Volume: NOT saved!')
        log_strings = ('Volume is -1. Aborting...',
                       'Volume is {}%. Saving...',
                       'Error saving profile "{}"',
                       'Error saving volume...')
        if self.volume == -1:
            ''' inform no change '''
            if (logger.isEnabledFor(logging.DEBUG)):
                logger.debug(log_strings[0])
            return ret_strings[0]
        elif self.volume == -2:
            if (logger.isEnabledFor(logging.DEBUG)):
                logger.debug(log_strings[3])
            return ret_strings[3]
        else:
            ''' change volume '''
            if (logger.isEnabledFor(logging.DEBUG)):
                logger.debug(log_strings[1].format(self.volume))
            config_file = self.config_files[0]
            ret_string = ret_strings[1].format(str(self.volume))
            if self.PLAYER_NAME == 'vlc':
                ret = self._write_config()
                if not ret:
                    ret_string = ret_strings[2]
            else:
                if os.path.exists(config_file):
                    if self._mplayer_on_windows7:
                        ''' we are on Windows7 with player
                            write global mplayer config section
                        '''
                        """ This is actually only for mplayer
                            which does not support profiles on Windows
                        """
                        lines_no_profile, lines_with_profile = \
                                self._split_config_file(config_file)
                        ind = [(i,x) for i,x in enumerate(lines_no_profile) if 'volume=' in x]
                        if ind:
                            lines_no_profile[ind[0][0]] = f'volume={self.volume}'
                        else:
                            lines_no_profile.append(f'volume={self.volume}\n')
                        try:
                            with open(config_file, "w", encoding='utf-8') as c_file:
                                c_file.write(
                                    '\n'.join(lines_no_profile) + \
                                    '\n'.join(lines_with_profile)
                                )
                            # self.volume = -1
                            self.PROFILE_FROM_USER = False
                            return ret_strings[1].format(str(self.volume))
                        except:
                            if (logger.isEnabledFor(logging.DEBUG)):
                                logger.debug(log_strings[2].format(config_file))
                            return ret_strings[2].format(str(self.volume))
                    else:
                        # logger.error('\n\nprofile_token = {}\n\n'.format(self.profile_token))
                        # logger.error(f'{self.PROFILE_FROM_USER}')
                        if self.PROFILE_FROM_USER:
                            ret = self._cnf.profile_manager.save_volume(
                                self.PLAYER_NAME, self.profile_token, self.volume
                            )
                            if ret is None:
                                return ret_strings[2].format(str(self.volume))
                            else:
                                self.volume = -1

            self.bck_win_player_config_file(config_file)
            return ret_string

    def _split_config_file(self, config_file):
        with open(config_file, 'r', encoding='utf-8') as c_file:
            config_string = c_file.read()
            config_string = config_string.replace('#Volume set from pyradio\n', '')
            lines = config_string.split('\n')
        no_comment_or_empty=[d for d in lines if d and not d.startswith('#')]
        l_ind=[(i,d) for i,d in enumerate(no_comment_or_empty) if d.startswith('[')]
        '''
            no global, with profiles:
                [(0, '[silent]'), (2, '[pyradio]')]
        '''

        if l_ind:
            lines_no_profile = lines[:l_ind[0][0]]
            lines_with_profile = lines[l_ind[0][0]:]
        else:
            lines_no_profile = []
            lines_with_profile = lines
        return lines_no_profile, lines_with_profile
        return lines_no_profile, lines_with_profile

    def bck_win_player_config_file(self, config_file=None):
        if platform.startswith('win'):
            ''' backup player config '''
            if config_file is None:
                cnf_file = self.config_files[0]
            else:
                cnf_file = config_file
            if os.path.exists(cnf_file):
                bck_file = os.path.join(os.getenv('APPDATA'), "pyradio", self.PLAYER_NAME + "-active.conf")
                try:
                    shutil_copy_file(cnf_file, bck_file)
                except:
                    pass

    def _restore_win_player_config_file(self):
        if platform.startswith('win'):
            ''' restore player config '''
            for k in ('mplayer', 'mpv'):
                bck_file = os.path.join(os.getenv('APPDATA'), "pyradio", k + "-active.conf")
                if os.path.exists(bck_file):
                    cnf_file = self.all_config_files[k][0]
                    try:
                        shutil_copy_file(bck_file, cnf_file)
                    except:
                        pass

    def _stop_delay_thread(self):
        if self.delay_thread is not None:
            try:
                self.delay_thread.cancel()
            except:
                pass
            self.delay_thread = None

    def _is_in_playback_token(self, a_string):
        for a_token in self._playback_token_tuple:
            if a_token in a_string:
                return True
        return False

    def _clear_empty_mkv(self):
        if self.recording > 0 and self.recording_filename:
            if os.path.exists(self.recording_filename):
                if os.path.getsize(self.recording_filename) == 0:
                    os.remove(self.recording_filename)

    def updateStatus(self, *args):
        stop = args[0]
        process = args[1]
        stop_player = args[2]
        detect_if_player_exited = args[3]
        enable_crash_detection_function = args[4]
        recording_lock = args[5]
        on_connect = args[6]
        log_player_input = args[7]
        has_error = False
        if (logger.isEnabledFor(logging.DEBUG)):
            logger.debug('updateStatus thread started.')
        #with lock:
        #    self.oldUserInput['Title'] = M_STRINGS['connecting_'] + self.name
        #    self.outputStream.write(msg=self.oldUserInput['Title'])
        ''' Force volume display even when icy title is not received '''
        with recording_lock:
            if self.buffering:
                self.oldUserInput['Title'] = M_STRINGS['buffering_'] + self.name
            else:
                self.oldUserInput['Title'] = M_STRINGS['playing_'] + self.name
        try:
            out = self.process.stdout
            while(True):
                http_error=False
                subsystemOutRaw = out.readline()
                with recording_lock:
                    try:
                        subsystemOut = subsystemOutRaw.decode(self._station_encoding, 'replace')
                    except:
                        subsystemOut = subsystemOutRaw.decode('utf-8', 'replace')
                with recording_lock:
                    is_accepted = self._is_accepted_input(subsystemOut)
                if logger.isEnabledFor(logging.DEBUG) and \
                        log_player_input() == 2:
                    logger.debug(
                        'PLAYER RAW: {} "{}"'.format(
                            ' . ' if is_accepted else 'xXx',
                            subsystemOut.strip()
                        )
                    )
                self._chapter_time = datetime.now()
                # logger.error('\nchecking\n{}\n'.format(subsystemOut))
                if stop():
                    break
                elif subsystemOut == '':
                    if logger.isEnabledFor(logging.INFO):
                        logger.info(f'----==== {self.PLAYER_NAME} got empty input ====----')
                    break
                elif not is_accepted:
                    continue
                elif '404' in subsystemOut and 'Not Available' in subsystemOut:
                    http_error = 404
                elif 'Name or service not known' in subsystemOut or \
                        "Couldn't resolve name for AF_INET:" in subsystemOut:
                        # ("Couldn't resolve name for AF_INET:" in subsystemOut and \
                        # "Couldn't resolve name for AF_INET6:" in subsystemOut):
                    http_error = 1005
                elif 'cannot connect to ' in subsystemOut:
                    http_error = 1006
                elif 'Server returned 503' in subsystemOut or \
                        '503 All backends failed or unhealthy' in subsystemOut or \
                        'HTTP 503 error' in subsystemOut:
                    http_error = 503
                elif 'debug: dead input' in subsystemOut or \
                        'Failed to open http' in subsystemOut or \
                        'debug: nothing to play' in subsystemOut:
                    http_error = 1001
                elif 'No stream found' in subsystemOut:
                    http_error = 1002
                elif 'Cannot find codec for audio format' in subsystemOut or \
                        'Audio: no sound' in subsystemOut:
                    http_error = 1008

                if http_error:
                    if logger.isEnabledFor(logging.INFO):
                        logger.info('----==== playbak stopped, reason: "{}" ====----'.format(subsystemOut.strip()))
                        if self.success_in_check_playlist is not None:
                            self.error_in_check_playlist(http_error)
                        else:
                            logger.error('1008 self.success_in_check_playlist is None')
                    break

                subsystemOut = subsystemOut.strip()
                subsystemOut = subsystemOut.replace('\r', '').replace('\n', '')
                # logger.error('DE subsystemOut = "{0}"'.format(subsystemOut))
                if logger.isEnabledFor(logging.DEBUG) and \
                        log_player_input() == 1:
                    logger.debug(f'PLAYER: "{subsystemOut}"')

                with recording_lock:
                    tmp = self.oldUserInput['Input']
                if tmp != subsystemOut:
                    with recording_lock:
                        self.oldUserInput['Input'] = subsystemOut
                        self_volume_string = self.volume_string
                    if self_volume_string in subsystemOut:
                        # disable volume for mpv
                        if self.PLAYER_NAME != 'mpv':
                            # logger.error('***** volume')
                            with recording_lock:
                                self_oldUserInput_Volume = self.oldUserInput['Volume']
                            if self_oldUserInput_Volume != subsystemOut:
                                with recording_lock:
                                    self.oldUserInput['Volume'] = subsystemOut
                                if self.PLAYER_NAME == 'vlc':
                                    if '.' in subsystemOut:
                                        token = '.'
                                    elif ',' in subsystemOut:
                                        token = ','
                                    else:
                                        token = ''
                                    if token:
                                        sp = subsystemOut.split(token)
                                        subsystemOut = sp[0]
                                with recording_lock:
                                    sp = subsystemOut.split(self_volume_string)
                                    self.volume = ''.join(c for c in sp[-1].split()[0] if c.isdigit())

                                    self_show_volume = self.show_volume
                                    self_oldUserInput_Title = self.oldUserInput['Title']
                                    # IMPORTANT: do this here, so that vlc actual_volume
                                    # gets updated in _format_volume_string
                                    string_to_show = self._format_volume_string(subsystemOut) + self._format_title_string(self.oldUserInput['Title'])

                                if self_show_volume and self_oldUserInput_Title:
                                    self.outputStream.write(msg_id=STATES.VOLUME, msg=string_to_show, counter='')
                                    self.threadUpdateTitle()
                    elif self._is_in_playback_token(subsystemOut):
                        self.stop_timeout_counter_thread = True
                        try:
                            self.connection_timeout_thread.join()
                        except:
                            pass
                        with recording_lock:
                            self.connecting = False
                        if enable_crash_detection_function:
                            enable_crash_detection_function()
                        with recording_lock:
                            if (not self.playback_is_on) and (logger.isEnabledFor(logging.INFO)):
                                logger.info('*** updateStatus(): Start of playback detected ***')
                            #if self.outputStream.last_written_string.startswith(M_STRINGS['connecting_']):
                            if self.oldUserInput['Title'] == '':
                                if self.buffering:
                                    new_input = M_STRINGS['buffering_'] + self.name
                                    msg_id=STATES.BUFFER
                                else:
                                    new_input = M_STRINGS['playing_'] + self.name
                                    msg_id=STATES.PLAY
                                    if self.success_in_check_playlist is not None:
                                        self.success_in_check_playlist()
                                    else:
                                        logger.error('1077 self.success_in_check_playlist is None')
                            else:
                                new_input = self.oldUserInput['Title']
                                logger.error(f'using msg_id=self.outputStream.current_msg_id: {self.outputStream.current_msg_id}')
                                if self.buffering:
                                    msg_id = STATES.BUFFER
                                else:
                                    msg_id = STATES.PLAY
                                    if self.success_in_check_playlist is not None:
                                        self.success_in_check_playlist()
                                    else:
                                        logger.error('1090 self.success_in_check_playlist is None')
                        if not self.playback_is_on:
                            on_connect()
                        self.outputStream.write(msg_id=msg_id, msg=new_input, counter='')
                        with recording_lock:
                            self.playback_is_on = True
                            self.connecting = False
                        self._stop_delay_thread()
                        self.stations_history_add_function()
                        if 'AO: [' in subsystemOut or \
                                'Stream buffering done' in subsystemOut or \
                                'Buffering ' in subsystemOut:
                            self.buffering = False
                            if self.PLAYER_NAME == 'vlc':
                                on_connect()
                            with self.buffering_lock:
                                self.buffering_change_function()
                            with self.status_update_lock:
                                self._icy_data['audio_format'] = subsystemOut.split('] ')[1].split(' (')[0]
                                self.info_display_handler()
                            if self.oldUserInput['Title'].startswith(M_STRINGS['buffering_']):
                                self.outputStream.write(
                                        msg_id=STATES.PLAY,
                                        msg=self.oldUserInput['Title'].replace(
                                            M_STRINGS['buffering_'],
                                            M_STRINGS['playing_']
                                            ),
                                        counter=''
                                        )
                                if self.success_in_check_playlist is not None:
                                    self.success_in_check_playlist()
                                else:
                                    logger.error('1122 self.success_in_check_playlist is None')
                        # logger.error('DE 3 {}'.format(self._icy_data))
                    elif self._is_icy_entry(subsystemOut):
                        if not subsystemOut.endswith('Icy-Title=(null)'):
                            if enable_crash_detection_function:
                                enable_crash_detection_function()
                            # logger.error('***** icy_entry: "{}"'.format(subsystemOut))
                            title = self._format_title_string(subsystemOut)
                            # logger.error('DE title = "{}"'.format(title))
                            ok_to_display = False
                            self.stop_timeout_counter_thread = True
                            try:
                                self.connection_timeout_thread.join()
                            except:
                                pass
                            if not self.playback_is_on:
                                if logger.isEnabledFor(logging.INFO):
                                    logger.info('*** updateStatus(): Start of playback detected (Icy-Title received) ***')
                                    on_connect()
                            with self.status_update_lock:
                                self.playback_is_on = True
                                self.connecting = False
                            self._stop_delay_thread()
                            self.stations_history_add_function()
                            ''' detect empty Icy-Title '''
                            title_without_prefix = title[len(self.icy_title_prefix):].strip()
                            # logger.error('DE title_without_prefix = "{}"'.format(title_without_prefix))
                            if title_without_prefix:
                                #self._stop_delay_thread()
                                # logger.error("***** updating title")
                                if title_without_prefix.strip() == '-':
                                    ''' Icy-Title is empty '''
                                    if logger.isEnabledFor(logging.DEBUG):
                                        logger.debug('Icy-Title = " - ", not displaying...')
                                else:
                                    self.oldUserInput['Title'] = title
                                    # make sure title will not pop-up while Volume value is on
                                    if self.delay_thread is None:
                                        ok_to_display = True
                                    # if self.PLAYER_NAME != 'vlc':
                                    #     self.buffering = False
                                    #     with self.buffering_lock:
                                    #         self.buffering_change_function()
                                    if ok_to_display and self.playback_is_on:
                                        string_to_show = self.title_prefix + title
                                        self.outputStream.write(msg_id=STATES.TITLE, msg=string_to_show, counter='')
                                        if self.success_in_check_playlist is not None:
                                            self.success_in_check_playlist()
                                        else:
                                            logger.error('1008 self.success_in_check_playlist is None')
                                    else:
                                        if logger.isEnabledFor(logging.DEBUG):
                                            logger.debug(f'***** Title change inhibited: ok_to_display = {ok_to_display}, playbabk_is_on = {self.playback_is_on}')
                            else:
                                ok_to_display = True
                                if (logger.isEnabledFor(logging.INFO)):
                                    logger.info('Icy-Title is NOT valid')
                                if ok_to_display and self.playback_is_on:
                                    # logger.error('\n\nhere - self.buffering: {}'.format(self.buffering))
                                    if self.buffering:
                                        title = M_STRINGS['buffering_'] + self.name
                                        msg_id = STATES.BUFFER
                                        # logger.error('buffering')
                                    else:
                                        title = M_STRINGS['playing_'] + self.name
                                        msg_id = STATES.PLAY
                                        if self.success_in_check_playlist is not None:
                                            self.success_in_check_playlist()
                                        else:
                                            logger.error('1008 self.success_in_check_playlist is None')
                                        # logger.error('playing')
                                    self.oldUserInput['Title'] = title
                                    string_to_show = self.title_prefix + title
                                    self.outputStream.write(msg_id=msg_id, msg=string_to_show, counter='')
                    #else:
                    #    if self.oldUserInput['Title'] == '':
                    #        self.oldUserInput['Title'] = M_STRINGS['connecting_'] + self.name
                    #        self.outputStream.write(msg=self.oldUserInput['Title'], counter='')

                    else:
                        for a_token in self.icy_audio_tokens:
                            if a_token in subsystemOut:
                                if not self.playback_is_on:
                                    if logger.isEnabledFor(logging.INFO):
                                        logger.info('*** updateStatus(): Start of playback detected (Icy audio token received) ***')
                                        on_connect()
                                self.stop_timeout_counter_thread = True
                                try:
                                    self.connection_timeout_thread.join()
                                except:
                                    pass
                                self.playback_is_on = True
                                self.connecting = False
                                self.stations_history_add_function()
                                if enable_crash_detection_function:
                                    enable_crash_detection_function()
                                # logger.error('DE token = "{}"'.format(a_token))
                                # logger.error('DE icy_audio_tokens[a_token] = "{}"'.format(self.icy_audio_tokens[a_token]))
                                a_str = subsystemOut.split(a_token)
                                # logger.error('DE str = "{}"'.format(a_str))
                                with self.status_update_lock:
                                    if self.icy_audio_tokens[a_token] == 'icy-br':
                                        self._icy_data[self.icy_audio_tokens[a_token]] = a_str[1].replace('kbit/s', '')
                                    else:
                                        self._icy_data[self.icy_audio_tokens[a_token]] = a_str[1]
                                    if self.icy_audio_tokens[a_token] == 'codec':
                                        if '[' in self._icy_data['codec']:
                                            self._icy_data['codec-name'] = self._icy_data['codec'].split('] ')[0].replace('[', '')
                                            self._icy_data['codec'] = self._icy_data['codec'].split('] ')[1]
                                    if 'codec-name' in self._icy_data:
                                        self._icy_data['codec-name'] = self._icy_data['codec-name'].replace('"', '')
                                # logger.error('DE audio data\n\n{}\n\n'.format(self._icy_data))
                        try:
                            if self._can_update_br(self._icy_data['icy-br']):
                                self.update_bitrate(self._icy_data['icy-br'])
                        except KeyError:
                            pass
                        self.info_display_handler()
        except:
            if logger.isEnabledFor(logging.ERROR):
                logger.error('Error in updateStatus thread.', exc_info=True)
            # return

        ''' crash detection '''
        if not stop():
            if detect_if_player_exited():
                if logger.isEnabledFor(logging.INFO):
                    logger.info('----==== player disappeared ====----')
                stop_player(
                    from_update_thread=True,
                    player_disappeared=True,
                    http_error=http_error
                )
            else:
                if logger.isEnabledFor(logging.INFO):
                    logger.info('Crash detection is off; waiting to timeout')
        if (logger.isEnabledFor(logging.INFO)):
            logger.info('updateStatus thread stopped.')
        self._clear_empty_mkv()

    def updateRecordingStatus(self, *args):
        stop = args[0]
        process = args[1]
        recording_lock = args[2]
        log_player_input = args[3]
        has_error = False
        if (logger.isEnabledFor(logging.DEBUG)):
            logger.debug('updateRecordingStatus thread started.')
        #with lock:
        #    self.oldUserInput['Title'] = M_STRINGS['connecting_'] + self.name
        #    self.outputStream.write(msg=self.oldUserInput['Title'])
        ''' Force volume display even when icy title is not received '''
        # self.oldUserInput['Title'] = M_STRINGS['playing_'] + self.name
        try:
            out = self.monitor_process.stdout
            while(True):
                subsystemOutRaw = out.readline()
                with recording_lock:
                    try:
                        subsystemOut = subsystemOutRaw.decode(self._station_encoding, 'replace')
                    except:
                        subsystemOut = subsystemOutRaw.decode('utf-8', 'replace')
                if subsystemOut == '':
                    break
                subsystemOut = subsystemOut.strip()
                subsystemOut = subsystemOut.replace('\r', '').replace('\n', '')
                if logger.isEnabledFor(logging.DEBUG) and \
                        log_player_input == 1:
                    logger.debug('RECORDER: "{}"'.format(subsystemOut.strip()))
                if stop():
                    break
                with recording_lock:
                    is_accepted = self._is_accepted_input(subsystemOut)
                if logger.isEnabledFor(logging.DEBUG) and \
                        log_player_input == 2:
                    logger.debug(
                        'RECORDER RAW: {} "{}"'.format(
                            ' . ' if is_accepted else 'xXx',
                            subsystemOut.strip()
                        )
                    )
                if not is_accepted:
                    if stop():
                        break
                    continue

                if stop():
                    break
                with recording_lock:
                    tmp = self.oldUserInput['Input']
                if tmp != subsystemOut:
                    if stop():
                        break
                    with recording_lock:
                        self.oldUserInput['Input'] = subsystemOut
                        self_volume_string = self.volume_string
                        self_player_name = self.PLAYER_NAME
                    if stop():
                        break
                    if self_volume_string in subsystemOut:
                        # disable volume for mpv
                        if self_player_name != 'mpv':
                            # logger.error('***** volume')
                            if stop():
                                break
                            with recording_lock:
                                if self.oldUserInput['Volume'] != subsystemOut:
                                    self.oldUserInput['Volume'] = subsystemOut
                                    if self_player_name == 'vlc':
                                        if '.' in subsystemOut:
                                            token = '.'
                                        elif ',' in subsystemOut:
                                            token = ','
                                        else:
                                            token = ''
                                        if token:
                                            sp = subsystemOut.split(token)
                                            subsystemOut = sp[0]
                                self.volume = ''.join(c for c in subsystemOut if c.isdigit())

                                # IMPORTANT: do this here, so that vlc actual_volume
                                # gets updated in _format_volume_string
                                string_to_show = self._format_volume_string(subsystemOut) + self._format_title_string(self.oldUserInput['Title'])

                                if self.show_volume and self.oldUserInput['Title']:
                                    self.outputStream.write(msg_id=STATES.VOLUME, msg=string_to_show, counter='')
                                    self.threadUpdateTitle()
                            if stop():
                                break
        except:
            if logger.isEnabledFor(logging.ERROR):
                logger.error('Error in updateRecordingStatus thread.', exc_info=True)
            # return

        if (logger.isEnabledFor(logging.INFO)):
            logger.info('updateRecordingStatus thread stopped.')

    def updateMPVStatus(self, *args):
        stop = args[0]
        process = args[1]
        stop_player = args[2]
        detect_if_player_exited = args[3]
        enable_crash_detection_function = args[4]
        log_player_input = args[5]
        if (logger.isEnabledFor(logging.DEBUG)):
            logger.debug('MPV updateStatus thread started.')

        sock = None
        while True:
            try:
                sock = self._connect_to_socket(self.mpvsocket)
            finally:
                if sock:
                    break
                if stop():
                    if (logger.isEnabledFor(logging.INFO)):
                        logger.info('MPV updateStatus thread stopped (no connection to socket).')
                    return
        # Send data
        message = b'{ "command": ["observe_property", 1, "metadata"] }\n'
        try:
            if platform.startswith('win'):
                win32file.WriteFile(sock, message)
            else:
                sock.sendall(message)
            go_on = True
        except:
            # logger.error('DE \n\nBroken pipe\n\n')
            go_on = False
        if go_on:
            while True:
                if stop():
                    break
                try:
                    if platform.startswith('win'):
                        try:
                            data = win32file.ReadFile(sock, 64*1024)
                        except pywintypes.error:
                            data = b''
                    else:
                        try:
                            data = sock.recvmsg(4096)
                        except:
                            data = b''
                    self._chapter_time = datetime.now()
                    a_data = self._fix_returned_data(data)
                    if logger.isEnabledFor(logging.DEBUG) and \
                            log_player_input() > 0:
                        logger.debug('PLAYER: "%r"', a_data)
                    http_error = False
                    if b'unrecognized file format' in a_data:
                        http_error = 1004
                        if logger.isEnabledFor(logging.INFO):
                            logger.info(f'----==== playbak stopped, reason: "{a_data}" ====----')
                    if b'"file_error":"unrecognized file format"' in a_data:
                        http_error = 1008
                        break
                    if b'"request_id":700' in a_data:
                        if b'"error":"success"' in a_data:
                            # logger.error('it is valid!')
                            if logger.isEnabledFor(logging.INFO):
                                logger.info(f'----==== playbak stopped, reason: "{a_data}" ====----')
                            ''' try to parse it '''
                            if b'HTTP Error 404' in a_data or \
                                    b'HTTPError 404' in a_data or \
                                    b'Not Found' in a_data:
                                http_error = 404
                            elif b'HTTP Error 403' in a_data or \
                                    b'HTTPError 403' in a_data or \
                                    b'Forbidden' in a_data:
                                http_error = 403
                            elif b'HTTP Error 503' in a_data or \
                                    b'HTTPError 503' in a_data or \
                                    b'All backends failed or unhealthy' in a_data:
                                http_error = 503
                            elif b'[Errno 110]' in a_data:
                                http_error = 1001
                            elif b'[Errno 104]' in a_data or \
                                    b'[Errno 111]' in a_data:
                                http_error = 1003
                            elif b'[Errno -2]' in a_data or \
                                    b'[Errno -3]' in a_data:
                                http_error = 1005
                            elif b'[Errno 101]' in a_data or \
                                    b'[Errno 113]' in a_data:
                                http_error = 1006
                            elif b'[Errno 13]' in a_data:
                                http_error = 1007
                            else:
                                if logger.isEnabledFor(logging.INFO):
                                    logger.info('----==== HTTP Error Message not handled ====----')
                                http_error = 1001

                    if http_error:
                        if self.success_in_check_playlist is not None:
                            self.error_in_check_playlist(http_error)
                        else:
                            logger.error('1008 self.success_in_check_playlist is None')
                        break

                    if stop():
                        break
                    elif b'"file_error":"loading failed"' in a_data:
                        self._request_mpv_error(sock)
                    elif a_data == b'':
                        if logger.isEnabledFor(logging.INFO):
                            logger.info('----==== MPV got empty input ====----')
                        break
                    if a_data:
                        all_data = a_data.split(b'\n')
                        d = None
                        for n in all_data:
                            if n == b'':
                                continue
                            if self._get_mpv_metadata(n, stop, enable_crash_detection_function):
                                self._request_mpv_info_data(sock)
                            # if True:
                            else:
                                try:
                                    if stop():
                                        break
                                    d = json.loads(n)
                                    if 'event' in d.keys():
                                        # logger.info('metadata-update\n\n')
                                        if d['event'] == 'metadata-update':
                                            # logger.info('{}\n\n'.format(d['event']))
                                            try:
                                                self._request_mpv_info_data_counter = 0
                                                if platform.startswith('win'):
                                                    win32file.WriteFile(sock, self.GET_TITLE)
                                                else:
                                                    sock.sendall(self.GET_TITLE)
                                            except:
                                                self._request_mpv_info_data_counter = 4
                                            ret = self._set_mpv_playback_is_on(stop, enable_crash_detection_function)
                                            if not ret:
                                                break
                                            self._request_mpv_info_data(sock)
                                            self.info_display_handler()
                                        elif d['event'] == 'playback-restart':
                                            # logger.info('====== playback-restarted\n{}\n\n'.format(self.oldUserInput))
                                            # logger.info('{}\n\n'.format(d['event']))
                                            self.buffering = False
                                            with self.buffering_lock:
                                                self.buffering_change_function()
                                            if not self.playback_is_on:
                                                ret = self._set_mpv_playback_is_on(stop, enable_crash_detection_function)
                                            if not ret:
                                                break
                                            self._request_mpv_info_data(sock)
                                            self.info_display_handler()
                                            if self.oldUserInput['Title'].startswith(M_STRINGS['buffering_']):
                                                self.outputStream.write(
                                                        msg_id=STATES.PLAY,
                                                        msg=self.oldUserInput['Title'].replace(
                                                            M_STRINGS['buffering_'],
                                                            M_STRINGS['playing_']
                                                        ),
                                                        counter=''
                                                        )
                                                if self.success_in_check_playlist is not None:
                                                    self.success_in_check_playlist()
                                                else:
                                                    logger.error('1008 self.success_in_check_playlist is None')
                                        elif (d['event'] == 'file-loaded' or \
                                                d['event'] == 'audio-reconfig') and \
                                                self.buffering:
                                            ''' buffering '''
                                            # logger.info('{}\n\n'.format(d['event']))
                                            if self.buffering and not self.playback_is_on:
                                                logger.info('sending playback is on')
                                                ret = self._set_mpv_playback_is_on(stop, enable_crash_detection_function)
                                            if not ret:
                                                break
                                            self.info_display_handler()
                                except:
                                    pass
                finally:
                    pass
        self._close_pipe(sock)

        if not stop():
            ''' haven't been asked to stop '''
            if detect_if_player_exited():
                if logger.isEnabledFor(logging.INFO):
                    logger.info('----==== MPV disappeared ====----')
                stop_player(
                    from_update_thread=True,
                    player_disappeared = True,
                    http_error=http_error
                )
            else:
                if logger.isEnabledFor(logging.INFO):
                    logger.info('Crash detection is off; waiting to timeout')
        if (logger.isEnabledFor(logging.INFO)):
            logger.info('MPV updateStatus thread stopped.')
        self._clear_empty_mkv()

    def _close_pipe(self, sock):
        if platform.startswith('win'):
            win32file.CloseHandle(sock)
        else:
            sock.close()

    def updateWinVLCStatus(self, *args):
        def do_crash_detection(detect_if_player_exited, stop):
            if self.playback_is_on:
                poll = process.poll()
                if poll is not None:
                    if not stop():
                        if detect_if_player_exited():
                            if logger.isEnabledFor(logging.INFO):
                                logger.info('----==== VLC disappeared ====----')
                            try:
                                stop_player(from_update_thread=True)
                            except:
                                pass
                            return True
                        else:
                            if logger.isEnabledFor(logging.INFO):
                                logger.info('Crash detection is off; waiting to timeout')
            return False
        has_error = False
        if (logger.isEnabledFor(logging.DEBUG)):
            logger.debug('Win VLC updateStatus thread started.')
        fn = args[0]
        enc = args[1]
        stop = args[2]
        process = args[3]
        stop_player = args[4]
        detect_if_player_exited = args[5]
        enable_crash_detection_function = args[6]
        on_connect = args[7]
        log_player_input = args[8]
        ''' Force volume display even when icy title is not received '''
        if self.buffering:
            self.oldUserInput['Title'] = M_STRINGS['buffering_'] + self.name
        else:
            self.oldUserInput['Title'] = M_STRINGS['playing_'] + self.name
        # logger.error('DE ==== {0}\n{1}\n{2}'.format(fn, enc, stop))
        #with lock:
        #    self.oldUserInput['Title'] = M_STRINGS['connecting_'] + self.name
        #    self.outputStream.write(msg=self.oldUserInput['Title'])

        go_on = False
        while not go_on:
            if stop():
                break
            try:
                fp = open(fn, mode='r', encoding=enc, errors='ignore')
                go_on = True
            except:
                pass

        try:
            while(True):
                if stop():
                    break
                # self._chapter_time = datetime.now()
                subsystemOut = fp.readline()
                subsystemOut = subsystemOut.strip().replace(u'\ufeff', '')
                subsystemOut = subsystemOut.replace('\r', '').replace('\n', '')
                if subsystemOut == '':
                    if do_crash_detection(detect_if_player_exited, stop):
                        break
                    continue
                if logger.isEnabledFor(logging.DEBUG) and \
                        log_player_input == 1:
                    logger.debug('PLAYER: "%s"', subsystemOut.strip())
                is_accepted = self._is_accepted_input(subsystemOut)
                if logger.isEnabledFor(logging.DEBUG) and \
                        log_player_input == 2:
                    logger.debug(
                        'PLAYER RAW: {} "{}"'.format(
                            ' . ' if is_accepted else 'xXx',
                            subsystemOut.strip()
                        )
                    )
                if not is_accepted:
                    continue
                if self.oldUserInput['Input'] != subsystemOut:
                    if stop():
                        break
                    self.oldUserInput['Input'] = subsystemOut
                    # logger.error('DE subsystemOut = "' + subsystemOut + '"')
                    if self.volume_string in subsystemOut:
                        if stop():
                            break
                        # logger.error("***** volume")
                        if self.oldUserInput['Volume'] != subsystemOut:
                            self.oldUserInput['Volume'] = subsystemOut
                            self.volume = ''.join(c for c in subsystemOut if c.isdigit())

                            # IMPORTANT: do this here, so that vlc actual_volume
                            # gets updated in _format_volume_string
                            string_to_show = self._format_volume_string(subsystemOut) + self._format_title_string(self.oldUserInput['Title'])

                            if self.show_volume and self.oldUserInput['Title']:
                                self.outputStream.write(msg_id=STATES.VOLUME, msg=string_to_show, counter='')
                                self.threadUpdateTitle()
                    elif self._is_in_playback_token(subsystemOut):
                        # logger.error('DE \n\ntoken = "' + subsystemOut + '"\n\n')
                        if stop():
                            break
                        self.stop_timeout_counter_thread = True
                        try:
                            self.connection_timeout_thread.join()
                        except:
                            pass
                        if enable_crash_detection_function:
                            enable_crash_detection_function()
                        if not self.playback_is_on:
                            if logger.isEnabledFor(logging.INFO):
                                logger.info('*** updateWinVLCStatus(): Start of playback detected ***')
                            on_connect()
                        #if self.outputStream.last_written_string.startswith(M_STRINGS['connecting_']):
                        if self.oldUserInput['Title'] == '':
                            if self.buffering:
                                new_input = M_STRINGS['buffering_'] + self.name
                                msg_id = STATES.BUFFER
                            else:
                                new_input = M_STRINGS['playing_'] + self.name
                                msg_id = STATES.PLAY
                                if self.success_in_check_playlist is not None:
                                    self.success_in_check_playlist()
                                else:
                                    logger.error('1008 self.success_in_check_playlist is None')
                        else:
                            new_input = self.oldUserInput['Title']
                            if self.buffering:
                                msg_id = STATES.BUFFER
                            else:
                                msg_id = STATES.PLAY
                                if self.success_in_check_playlist is not None:
                                    self.success_in_check_playlist()
                                else:
                                    logger.error('1008 self.success_in_check_playlist is None')
                        self.outputStream.write(msg_id=msg_id, msg=new_input, counter='')
                        self.playback_is_on = True
                        self.connecting = False
                        self._stop_delay_thread()
                        self.stations_history_add_function()
                        # logger.info('checking: "{}"'.format(subsystemOut))
                        if 'AO: [' in subsystemOut or \
                                'buffering done' in subsystemOut or \
                                'Buffering 100%' in subsystemOut:
                            if 'AO: [' in subsystemOut:
                                with self.status_update_lock:
                                    self._icy_data['audio_format'] = subsystemOut.split('] ')[1].split(' (')[0]
                                    self.info_display_handler()
                            if self.oldUserInput['Title'].startswith(M_STRINGS['buffering_']):
                                self.outputStream.write(
                                        msg_id=STATES.BUFFER,
                                        msg=self.oldUserInput['Title'].replace(
                                            M_STRINGS['buffering_'],
                                            M_STRINGS['playing_']
                                        ),
                                        counter=''
                                        )
                        # logger.error('DE 3 {}'.format(self._icy_data))
                    elif self._is_icy_entry(subsystemOut):
                        if stop():
                            break
                        if not self.playback_is_on:
                            self.stop_timeout_counter_thread = True
                            try:
                                self.connection_timeout_thread.join()
                            except:
                                pass
                            if logger.isEnabledFor(logging.INFO):
                                logger.info('*** updateWinVLCStatus(): Start of playback detected (Icy-Title received) ***')
                            if not self.playback_is_on:
                                on_connect()
                        self.stop_timeout_counter_thread = True
                        try:
                            self.connection_timeout_thread.join()
                        except:
                            pass
                        self.playback_is_on = True
                        self.connecting = False
                        self._stop_delay_thread()
                        self.stations_history_add_function()
                        if enable_crash_detection_function:
                            enable_crash_detection_function()

                        if not subsystemOut.endswith('Icy-Title=(null)'):
                            # logger.error("***** icy_entry")
                            title = self._format_title_string(subsystemOut)
                            ok_to_display = False
                            if title[len(self.icy_title_prefix):].strip():
                                self.oldUserInput['Title'] = title
                                # make sure title will not pop-up while Volume value is on
                                if self.delay_thread is None:
                                    ok_to_display = True
                                if ok_to_display and self.playback_is_on:
                                    string_to_show = self.title_prefix + title
                                    self.outputStream.write(msg_id=STATES.TITLE, msg=string_to_show, counter='')
                                    if self.success_in_check_playlist is not None:
                                        self.success_in_check_playlist()
                                    else:
                                        logger.error('1008 self.success_in_check_playlist is None')
                            else:
                                ok_to_display = True
                                if (logger.isEnabledFor(logging.INFO)):
                                    logger.info('Icy-Title is NOT valid')
                                if ok_to_display and self.playback_is_on:
                                    if self.buffering:
                                        title = M_STRINGS['buffering_'] + self.name
                                    else:
                                        title = M_STRINGS['playing_'] + self.name
                                    self.oldUserInput['Title'] = title
                                    string_to_show = self.title_prefix + title
                                    self.outputStream.write(msg_id=STATES.TITLE, msg=string_to_show, counter='')
                                    if self.success_in_check_playlist is not None:
                                        self.success_in_check_playlist()
                                    else:
                                        logger.error('1008 self.success_in_check_playlist is None')
                    #else:
                    #    if self.oldUserInput['Title'] == '':
                    #        self.oldUserInput['Title'] = M_STRINGS['connecting_'] + self.name
                    #        self.outputStream.write(msg=self.oldUserInput['Title'], counter='')

                    else:
                        if stop():
                            break
                        for a_token in self.icy_audio_tokens:
                            if a_token in subsystemOut:
                                self.stop_timeout_counter_thread = True
                                try:
                                    self.connection_timeout_thread.join()
                                except:
                                    pass
                                if not self.playback_is_on:
                                    if logger.isEnabledFor(logging.INFO):
                                        logger.info('*** updateWinVLCStatus(): Start of playback detected (Icy audio token received) ***')
                                    on_connect()
                                self.playback_is_on = True
                                self.connecting = False
                                self._stop_delay_thread()
                                self.stations_history_add_function()
                                if enable_crash_detection_function:
                                    enable_crash_detection_function()
                                # logger.error('DE token = "{}"'.format(a_token))
                                # logger.error('DE icy_audio_tokens[a_token] = "{}"'.format(self.icy_audio_tokens[a_token]))
                                a_str = subsystemOut.split(a_token)
                                # logger.error('DE str = "{}"'.format(a_str))
                                with self.status_update_lock:
                                    if self.icy_audio_tokens[a_token] == 'icy-br':
                                        self._icy_data[self.icy_audio_tokens[a_token]] = a_str[1].replace('kbit/s', '')
                                    else:
                                        self._icy_data[self.icy_audio_tokens[a_token]] = a_str[1]
                                    if self.icy_audio_tokens[a_token] == 'codec':
                                        if '[' in self._icy_data['codec']:
                                            self._icy_data['codec-name'] = self._icy_data['codec'].split('] ')[0].replace('[', '')
                                            self._icy_data['codec'] = self._icy_data['codec'].split('] ')[1]
                                    if 'codec-name' in self._icy_data:
                                        self._icy_data['codec-name'] = self._icy_data['codec-name'].replace('"', '')
                                # logger.error('DE audio data\n\n{}\n\n'.format(self._icy_data))
                        try:
                            if self._can_update_br(self._icy_data['icy-br']):
                                self.update_bitrate(self._icy_data['icy-br'])
                        except KeyError:
                            pass
                        self.info_display_handler()
        except:
            has_error = True
            if logger.isEnabledFor(logging.ERROR):
                logger.error('Error in Win VLC updateStatus thread.', exc_info=True)
        if has_error or not stop():
            do_crash_detection(detect_if_player_exited, stop)
        try:
            fp.close()
        except:
            pass
        self._clear_empty_mkv()

    def _request_mpv_error(self, sock):
        try:
            if platform.startswith('win'):
                win32file.WriteFile(sock, self.GET_ERROR)
            else:
                # sock.sendall(self.GET_ERROR)
                sock.sendall(self.GET_ERROR)
        except BrokenPipeError:
            pass

    def _request_mpv_info_data(self, sock):
        with self.status_update_lock:
            ret = len(self._icy_data) == 0
        if 'audio_format' not in self._icy_data or \
            'codec' not in self._icy_data or \
                'codec-name' not in self._icy_data:
            ret = True
        # if ret == 0 or force:
        if ret:
            # logger.error('\n\nIn _request_mpv_info_data')
            no_get_title_exception = True
            if platform.startswith('win'):
                if self._request_mpv_info_data_counter == 4:
                    try:
                        win32file.WriteFile(sock, self.GET_TITLE)
                    except BrokenPipeError:
                        no_get_title_exception = False
                try:
                    if 'audio_format' not in self._icy_data:
                        win32file.WriteFile(sock, self.GET_AUDIO_FORMAT)
                    if 'codec' not in self._icy_data:
                        win32file.WriteFile(sock, self.GET_AUDIO_CODEC)
                    if 'codec-name' not in self._icy_data:
                        win32file.WriteFile(sock, self.GET_AUDIO_CODEC_NAME)
                except BrokenPipeError:
                    pass
            else:
                if self._request_mpv_info_data_counter == 4:
                    try:
                        sock.sendall(self.GET_TITLE)
                    except BrokenPipeError:
                        no_get_title_exception = False
                try:
                    if 'audio_format' not in self._icy_data:
                        sock.sendall(self.GET_AUDIO_FORMAT)
                    if 'codec' not in self._icy_data:
                        sock.sendall(self.GET_AUDIO_CODEC)
                    if 'codec-name' not in self._icy_data:
                        sock.sendall(self.GET_AUDIO_CODEC_NAME)
                except BrokenPipeError:
                    pass
            if no_get_title_exception:
                self._request_mpv_info_data_counter += 1
                if self._request_mpv_info_data_counter >= 4:
                    self._request_mpv_info_data_counter = 0

    def _get_mpv_metadata(self, *args):
        ''' Get MPV metadata

            Parameters
            ==========
            a_data (args[0]
                Data read from socket
            lock (args[1])
                Thread lock
            stop (args[2])
                function to indicate thread stopping

            Returns
            =======
            True
                Manipulated no data (other functions must
                manipulate them)
            False
                Data read and manipulated, or stop condition
                triggered. Other functions do not have to deal
                with this data, of thread will terminate.

            Populates
            =========
            self._icy_data
                Fields:
                    icy-title        : Title of song (python 3 only)
                    icy-name         : Station name
                    icy-url          : Station URL
                    icy-genre        : Station genres
                    icy-br           : Station bitrate
                    audio_format     : XXXXHx stereo/mono 1/2ch format
                    artist, title    : Artist and Title of song (vorbis stations)
                    album, year      : Album and Year of song (vorbis stations)
        '''

        return_value = False
        a_data = args[0]
        stop = args[1]
        enable_crash_detection_function = args[2]
        if b'"icy-title":"' in a_data or \
                b'"title":"' in a_data:
            # if not self.playback_is_on:
            #     if stop():
            #         return False
            #     self._set_mpv_playback_is_on(stop, enable_crash_detection_function)
            if b'"icy-title":"' in a_data:
                title = a_data.split(b'"icy-title":"')[1].split(b'"}')[0]
            else:
                title = a_data.split(b'"title":"')[1].split(b'"}')[0].split(b'","')[0]
            if title:
                if title == b'-' or title == b' - ':
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug('Icy-Title = " - ", not displaying...')
                else:
                    if b'"artist":"' in a_data:
                        try:
                            artist = a_data.split(b'"artist":"')[1].split(b'"}')[0].split(b'","')[0]
                        except IndexError:
                            artist = None
                    else:
                        artist = None
                    if artist:
                        try:
                            self.oldUserInput['Title'] = M_STRINGS['title_'] + artist.decode(self._station_encoding, 'replace') + ' - ' + title.decode(self._station_encoding, 'replace')
                        except:
                            self.oldUserInput['Title'] = M_STRINGS['title_'] + artist.decode('utf-8', 'replace') + ' - ' + title.decode('utf-8', 'replace')
                    else:
                        try:
                            self.oldUserInput['Title'] = M_STRINGS['title_'] + title.decode(self._station_encoding, 'replace')
                        except:
                            self.oldUserInput['Title'] = M_STRINGS['title_'] + title.decode('utf-8', 'replace')
                    if b'"album":' in a_data:
                        try:
                            album = a_data.split(b'"album":"')[1].split(b'"}')[0].split(b'","')[0]
                            if album:
                                if b'"year":' in a_data:
                                    year = a_data.split(b'"year":"')[1].split(b'"}')[0].split(b'","')[0]
                                else:
                                    year = None
                                if year:
                                    try:
                                        self.oldUserInput['Title'] += ' [' + album.decode(self._station_encoding, 'replace') + ', ' + year.decode('utf-8', 'replace') + ']'
                                    except:
                                        self.oldUserInput['Title'] += ' [' + album.decode('utf-8', 'replace') + ', ' + year.decode('utf-8', 'replace') + ']'
                                else:
                                    try:
                                        self.oldUserInput['Title'] += ' [' + album.decode(self._station_encoding, 'replace') + ']'
                                    except:
                                        self.oldUserInput['Title'] += ' [' + album.decode('utf-8', 'replace') + ']'
                        except IndexError:
                            pass
                    string_to_show = self.title_prefix + self.oldUserInput['Title']
                    #logger.critical(string_to_show)
                    if stop():
                        return False
                    self.outputStream.write(msg_id=STATES.TITLE, msg=string_to_show, counter='')
                    if self.success_in_check_playlist is not None:
                        self.success_in_check_playlist()
                    else:
                        logger.error('1008 self.success_in_check_playlist is None')
                if not self.playback_is_on:
                    if stop():
                        return False
                    return_value = self._set_mpv_playback_is_on(stop, enable_crash_detection_function)
                    if not return_value:
                        return False
            else:
                if (logger.isEnabledFor(logging.INFO)):
                    logger.info('Icy-Title is NOT valid')
                self.buffering = False
                with self.buffering_lock:
                    self.buffering_change_function()
                title = M_STRINGS['playing_'] + self.name
                string_to_show = self.title_prefix + title
                if stop():
                    return False
                self.outputStream.write(msg_id=STATES.PLAY, msg=string_to_show, counter='')
                if self.success_in_check_playlist is not None:
                    self.success_in_check_playlist()
                else:
                    logger.error('1008 self.success_in_check_playlist is None')
                self.oldUserInput['Title'] = title

        # logger.info('DE a_data {}'.format(a_data))
        if b'icy-br' in a_data:
            # logger.info('DE check {}'.format(self._icy_data))
            if 'icy-br' not in self._icy_data:
                for icy in ('icy-name', 'icy-url', 'icy-genre', 'icy-br'):
                    if stop():
                        return False
                    bytes_icy = bytes(icy, encoding='utf-8')
                    if icy in ('icy-name', 'icy-genre'):
                        enc = self._station_encoding
                    else:
                    #     enc = 'utf-8'
                    # if icy == 'icy-br':
                        got_icy_br = True
                    if bytes_icy in a_data :
                        with self.status_update_lock:
                            try:
                                self._icy_data[icy] = a_data.split(bytes_icy + b'":"')[1].split(b'",')[0].split(b'"}')[0].decode(enc)
                            except (IndexError, UnicodeDecodeError):
                                pass
                    # logger.error('DE 0 {}'.format(self._icy_data))
            # if got_icy_br:
            try:
                if self._can_update_br(self._icy_data['icy-br']):
                    self.update_bitrate(self._icy_data['icy-br'])
            except KeyError:
                pass
            return True

        elif b'request_id' in a_data and b'"error":"success"' in a_data:
            if b'"request_id":200' in a_data:
                try:
                    d = json.loads(a_data)
                except:
                    d = None
                if d:
                    self.status_update_lock.acquire()
                    try:
                        self._icy_data['audio_format'] = '{0}Hz {1} {2}ch {3}'.format(
                                d['data']['samplerate'],
                                d['data']['channels'],
                                d['data']['channel-count'],
                                d['data']['format'])
                    finally:
                        self.status_update_lock.release()
            elif b'"request_id":300' in a_data:
                self.status_update_lock.acquire()
                try:
                    self._icy_data['codec'] = a_data.split(b'"data":"')[1].split(b'",')[0].decode('utf-8')
                except IndexError:
                    pass
                finally:
                    self.status_update_lock.release()
                self.info_display_handler()
            elif b'"request_id":400' in a_data:
                self.status_update_lock.acquire()
                try:
                    self._icy_data['codec-name'] = a_data.split(b'"data":"')[1].split(b'",')[0].decode('utf-8')
                except IndexError:
                    pass
                finally:
                    self.status_update_lock.release()
            # logger.error('DE 1 {}'.format(self._icy_data))
            self.info_display_handler()
            return True
        else:
            return return_value
            # return False

    def _set_mpv_playback_is_on(self, stop, enable_crash_detection_function):
        self.stop_timeout_counter_thread = True
        try:
            self.connection_timeout_thread.join()
        except:
            pass
        self.detect_if_player_exited = True
        if (not self.playback_is_on) and (logger.isEnabledFor(logging.INFO)):
            logger.info('*** _set_mpv_playback_is_on(): Start of playback detected ***')
        self.stop_timeout_counter_thread = True
        try:
            self.connection_timeout_thread.join()
        except:
            pass
        self.stations_history_add_function()
        # logger.info('self.buffering = {}'.format(self.buffering))
        if self.buffering:
            new_input = M_STRINGS['buffering_'] + self.name
            msg_id = STATES.BUFFER
        else:
            new_input = M_STRINGS['playing_'] + self.name
            msg_id = STATES.PLAY
            if self.success_in_check_playlist is not None:
                logger.error('1008 self.success_in_check_playlist is not None')
                self.success_in_check_playlist()
            else:
                logger.error('1008 self.success_in_check_playlist is None')
        self.outputStream.write(msg_id=msg_id, msg=new_input, counter='')
        with self.buffering_lock:
            self.buffering_change_function()
        if self.oldUserInput['Title'] == '':
            self.oldUserInput['Input'] = new_input
        self.oldUserInput['Title'] = new_input
        self.playback_is_on = True
        self.connecting = False
        if self.success_in_check_playlist is not None:
            self.success_in_check_playlist()
        else:
            logger.error('\n\nself.success_in_check_playlist is None\n\n')
        if stop():
            return False
        enable_crash_detection_function()
        return True

    def threadUpdateTitle(self, delay=1):
        if self.oldUserInput['Title'] != '':
            self._stop_delay_thread()
            try:
                self.delay_thread = threading.Timer(
                        delay,
                        self.updateTitle,
                        [ self.outputStream, None ]
                        )
                self.delay_thread.start()
            except:
                if (logger.isEnabledFor(logging.DEBUG)):
                    logger.debug('delay thread start failed')

    def updateTitle(self, *arg, **karg):
        self._stop_delay_thread()
        if arg[1]:
            arg[0].write(msg_id=STATES.TITLE, msg=arg[1])
        else:
            arg[0].write(msg_id=STATES.TITLE, msg=self.title_prefix + self._format_title_string(self.oldUserInput['Title']))
        if self.success_in_check_playlist is not None:
            self.success_in_check_playlist()
        else:
            logger.error('1008 self.success_in_check_playlist is None')

    def _is_icy_entry(self, a_string):
        for a_token in self.icy_tokens:
            if a_token in a_string:
                return True
        return False

    def _format_title_string(self, title_string):
        return self._title_string_format_text_tag(title_string)

    def _title_string_format_text_tag(self, a_string):
        # logger.error('\n...\n...\na_string: "{}"'.format(a_string))
        if 'Metadata update for StreamTitle: ' in a_string:
            ''' mplayer verbose... '''
            sp = a_string.split('Metadata update for StreamTitle: ')
            try:
                final_text_string = self.icy_title_prefix + sp[1]
                # logger.error('final_text_string: "{}"'.format(final_text_string))
                return final_text_string
            except IndexError:
                pass

        i = a_string.find(' - text="')
        if i == -1:
            return a_string
        else:
            ret_string = a_string[:i]
            text_string = a_string[i+9:]
            final_text_string = text_string[:text_string.find('"')]
            if ret_string == self.icy_title_prefix + final_text_string:
                return ret_string
            else:
                return ret_string + ': ' + final_text_string

    def _format_volume_string(self, volume_string):
        return self._title_string_format_text_tag(volume_string)

    def isPlaying(self):
        return bool(self.process)

    def _start_monitor_update_thread(self):
        self.monitor_update_thread = threading.Thread(
            target=self.updateRecordingStatus,
            args=(
                lambda: self.stop_mpv_status_update_thread,
                self.monitor_process,
                self._recording_lock,
                lambda: self._cnf.debug_log_player_input
            )
        )
        ''' make sure the counter is stopped
            and a message other than "Connecting..."
            is displayed
        '''
        with self._recording_lock:
            self.stop_timeout_counter_thread = True
            self.connecting = False
            self.playback_is_on = True
            the_title = self.oldUserInput['Title']
        self.outputStream.write(msg_id=STATES.TITLE, msg=the_title, counter='')
        if self.success_in_check_playlist is not None:
            self.success_in_check_playlist()
        else:
            logger.error('1008 self.success_in_check_playlist is None')
        # self.threadUpdateTitle()
        self.monitor_update_thread.start()

    def play(self,
             a_station,
             stop_player,
             detect_if_player_exited,
             enable_crash_detection_function=None,
             encoding='',
             referer=None
         ):
        self._buffering_data = None
        name = a_station[0]
        if encoding:
            a_station[Station.encoding] = encoding
        if referer:
            a_station[Station.referer] = referer
        # logger.error('')
        # logger.error('params = {}'.format(self.params))
        # logger.error('')
        ''' use a multimedia player to play a stream '''
        self.monitor = self.monitor_process = self.monitor_opts = None
        # logger.error('self.monitor_process.pid = {}'.format(self.monitor_process))
        self.recording_filename = ''
        self.volume = -1
        self.close()
        self.name = name
        self.station_volume = int(a_station[Station.volume]) if a_station[Station.volume] and self.enable_per_station_volume else -1
        self.oldUserInput = {'Input': '', 'Volume': '', 'Title': ''}
        self.muted = self.paused = False
        self.show_volume = True
        self.title_prefix = ''
        self.playback_is_on = False
        self.delay_thread = None
        self.outputStream.write(msg_id=STATES.CONNECT, msg=M_STRINGS['station_'] + name + M_STRINGS['station-open'], counter='')
        if logger.isEnabledFor(logging.INFO):
            logger.info('Selected Station: ' + name)
        if encoding:
            self._station_encoding = encoding
        else:
            self._station_encoding = self.config_encoding
        opts = []
        isPlayList = a_station[Station.url].split("?")[0][-3:] in ['m3u', 'pls']

        # get buffering data from station data
        if a_station[Station.buffering].startswith('0'):
            self._buffering_data = None
        else:
            try:
                sp = a_station[Station.buffering].split('@')
                delay = self._calculate_buffer_size_in_kb(*sp)
                x = PlayerCache(
                        self.PLAYER_NAME,
                        self._cnf.state_dir,
                        lambda: self.recording
                        )
                x.delay = delay
                self._buffering_data = x.cache[:]
                x = None
            except ValueError:
                self._buffering_data = None

        opts, self.monitor_opts, referer, referer_file = self._buildStartOpts(
            a_station, playList=isPlayList
        )
        self.stop_mpv_status_update_thread = False
        if logger.isEnabledFor(logging.INFO):
            logger.info('Executing command: %s', ' '.join(opts))

        if self._cnf.USE_EXTERNAL_PLAYER:
            ''' do not start the player, just return opts '''
            return opts

        if platform.startswith('win') and self.PLAYER_NAME == 'vlc':
            self.stop_win_vlc_status_update_thread = False
            ''' Launches vlc windowless '''
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.process = subprocess.Popen(opts, shell=False,
                                            startupinfo=startupinfo)
            self.update_thread = threading.Thread(
                target=self.updateWinVLCStatus,
                args=(
                    self._vlc_stdout_log_file,
                    self.config_encoding,
                    lambda: self.stop_win_vlc_status_update_thread,
                    self.process,
                    stop_player,
                    detect_if_player_exited,
                    enable_crash_detection_function,
                    self._on_connect,
                    lambda: self._cnf.debug_log_player_input
                )
            )
        else:
            if self.PLAYER_NAME == 'mpv':
                self._request_mpv_info_data_counter = 0
                self.process = subprocess.Popen(opts, shell=False,
                                                stdout=subprocess.DEVNULL,
                                                stdin=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL)
                self.update_thread = threading.Thread(
                    target=self.updateMPVStatus,
                    args=(lambda: self.stop_mpv_status_update_thread,
                          self.process,
                          stop_player,
                          detect_if_player_exited,
                          enable_crash_detection_function,
                          lambda: self._cnf.debug_log_player_input
                    )
                )
            else:
                self.process = subprocess.Popen(
                    opts, shell=False,
                    stdout=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )
                self.update_thread = threading.Thread(
                    target=self.updateStatus,
                    args=(
                        lambda: self.stop_mpv_status_update_thread,
                        self.process,
                        stop_player,
                        detect_if_player_exited,
                        enable_crash_detection_function,
                        self._recording_lock,
                        self._on_connect,
                        lambda: self._cnf.debug_log_player_input
                    )
                )
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'Started Player with PID = {self.process.pid}')
        self.update_thread.start()
        if self.PLAYER_NAME == 'vlc':
            if self.WIN:
                pass
                # if self.process:
                #     self._thrededreq('volume 0\n')
                #     self._thrededreq('add ' + self._vlc_url + '\n')
                # threading.Thread(target=self._remove_vlc_stdout_log_file, args=()).start()
            else:
                self._sendCommand('volume 0\n')
                self._sendCommand('add ' + self._vlc_url + '\n')
            self.get_volume()

        if self._recording > 0:
            ''' start chapters logger '''
            if self._chapters is None:
                self._chapters = PyRadioChapters(
                        self._cnf,
                        chapter_time=lambda: self._chapter_time
                        )
            self._chapters.clear()
            self.log.add_chapters_function = self._chapters.add_function()
            if self.log.add_chapters_function:
                self._chapters.add(name)
        else:
            self.log.add_chapters_function = None

        # start playback check timer thread
        self.stop_timeout_counter_thread = False
        if self.playback_timeout > 0:
            ''' set connecting here insead of Player.play()
                so that we do not use it when timeout = 0
            '''
            self.connecting = True
            try:
                self.connection_timeout_thread = threading.Thread(
                    target=self.playback_timeout_counter,
                    args=(self.playback_timeout,
                          self.name,
                          lambda: self.stop_timeout_counter_thread)
                )
                self.connection_timeout_thread.start()
                if (logger.isEnabledFor(logging.DEBUG)):
                    logger.debug('playback detection thread started')
            except:
                self.connecting = False
                self.connection_timeout_thread = None
                if (logger.isEnabledFor(logging.ERROR)):
                    logger.error('playback detection thread failed to start')
        else:
            self.connecting = False
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('playback detection thread not starting (timeout is 0)')
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'----==== {self.PLAYER_NAME} player started ====----')
        self.currently_recording = True if self.recording > 0 else False
        if self.recording == self.RECORD_AND_LISTEN \
                and self.PLAYER_NAME != 'mpv':
            self.buffering = False
            # logger.error('=======================\n\n')
            limit = 120000
            if self.PLAYER_NAME == 'mplayer':
                if not platform.startswith('win'):
                    limit = 12000
                threading.Thread(
                        target=self.create_monitor_player,
                        args=(lambda: self.stop_mpv_status_update_thread or \
                                self.stop_win_vlc_status_update_thread,
                              limit,
                              self._start_monitor_update_thread)
                        ).start()
            else:
                threading.Thread(
                        target=self.create_monitor_player,
                        args=(lambda: self.stop_mpv_status_update_thread,  limit, self._start_monitor_update_thread)
                        ).start()
            # logger.error('=======================\n\n')
        if referer_file:
            self.handle_old_referer(referer, referer_file)

    def _sendCommand(self, command):
        ''' send keystroke command to player '''
        if [x for x in ('q', 'shutdown') if command.startswith(x)]:
            self._command_to_player(self.process, command)
            # logger.error('self.monitor_process.pid = {}'.format(self.monitor_process))
            if self.monitor_process is not None:
                self._command_to_player(self.monitor_process, command)
            return
        # logger.error('self.monitor_process.pid = {}'.format(self.monitor_process))
        if self.monitor_process is not None and \
            [x for x in
             ('/', '*', 'p', 'm', 'vol', 'pause') if command.startswith(x)
             ]:
            # logger.error('\n\nsending command: "{}"\n\n'.format(command))
            self._command_to_player(self.monitor_process, command)
        else:
            self._command_to_player(self.process, command)

    def _command_to_player(self, a_process, command):
        if a_process is None:
            return

        # Check if the process has terminated
        if a_process.poll() is not None:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Cannot send command; process has terminated. Command: {command}".strip())
            return

        # Optionally check if stdin is valid and open
        if a_process.stdin is None or getattr(a_process.stdin, "closed", False):
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Cannot send command; process's stdin is closed. Command: {command}".strip())
            return

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Sending Command: {command}".strip())
        try:
            # Write the command to the process's standard input
            a_process.stdin.write(command.encode('utf-8', 'replace'))
            a_process.stdin.flush()
        except Exception:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f"Error while sending Command: {command}".strip())

    def close_from_windows(self):
        ''' kill player instance when window console is closed '''
        self.currently_recording = False
        if self.process:
            self.close()
            self._stop()

    def close(self, player_disappeared=False):
        self.currently_recording = False
        ''' kill player instance '''
        self._no_mute_on_stop_playback(player_disappeared)

        ''' First close the subprocess '''
        self._stop(player_disappeared)
        ''' Here is fallback solution and cleanup '''
        self.stop_timeout_counter_thread = True
        try:
            self.connection_timeout_thread.join()
        except:
            pass
        self._stop_delay_thread()
        if self.process is not None:
            self._kill_process_tree(self.process.pid)
            try:
                self.process.wait()
            except:
                pass
            finally:
                self.process = None
            try:
                self.update_thread.join()
            except:
                pass
            finally:
                self.update_thread = None
        if self.monitor_process is not None:
            self._kill_process_tree(self.monitor_process.pid)
            try:
                self.monitor_process.wait()
            except:
                pass
            finally:
                self.monitor_process = None
            try:
                self.monitor_update_thread.join()
            except:
                pass
            finally:
                self.monitor_update_thread = None
        self.monitor = self.monitor_process = self.monitor_opts = None

    def _kill_process_tree(self, pid):
        if psutil.pid_exists(pid):
            parent = psutil.Process(pid)
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'PID {pid} does not exist...')
            return
        try:
            children = parent.children(recursive=True)
            try:
                os.kill(parent.pid, 9)
            except:
                pass
            for child in children:
                try:
                    os.kill(child.pid, 9)
                except:
                    pass
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'PID {pid} (and its children)  killed...')
        except psutil.NoSuchProcess:
            pass

    def _killall(self, name):
        if name:
            try:
                # iterating through each instance of the process
                for line in os.popen("ps ax | grep " + name + " | grep -v grep"):
                    fields = line.split()
                    if name in fields[4]:
                        # extracting Process ID from the output
                        pid = fields[0]

                        # terminating process
                        # os.kill(int(pid), signal.SIGKILL)
                        os.kill(int(pid), 9)
                        # os.kill(int(pid), 15)
            except:
                pass

    def _calculate_buffer_size_in_kb(self, delay_seconds, bitrate_kbps=None):
        ''' return delay in seconds for mpv and vlc '''
        if '@' in delay_seconds:
            sp = delay_seconds.split('@')
            delay_seconds = sp[0]
        return delay_seconds

    def _buildStartOpts(self, a_station, playList):
        pass

    def _get_referer(self, streamName, streamReferer):
        referer = None
        referer_file = os.path.join(self._cnf.xdg.stations_dir, streamName + '.referer.txt')
        if os.path.exists(referer_file):
            try:
                with open(referer_file, 'r', encoding='utf-8') as f:
                    referer = f.read().strip()
            except:
                referer_file = None
        else:
            referer_file = None
        logger.error(f'{streamReferer = }')
        if streamReferer:
            referer = streamReferer
        return referer, referer_file

    def togglePause(self):
        if self.PLAYER_NAME == 'mpv':
            self.paused = self._pause()
        elif self.PLAYER_NAME == 'vlc':
            self.paused = not self.paused
            self._pause()
        else:
            self.paused = not self.paused
            self._pause()
        if self.paused:
            # self._stop_delay_thread()
            self.title_prefix = '[Paused] '
            self.show_volume = False
            self.muted = False
        else:
            self.title_prefix = ''
            self.show_volume = True
        # logger.info('\n\nself.paused = {}\n\n'.format(self.paused))
        if self.oldUserInput['Title'] == '':
            self.outputStream.write(msg_id=STATES.TITLE, msg=self.title_prefix + self._format_title_string(self.oldUserInput['Input']), counter='')
        else:
            self.outputStream.write(msg_id=STATES.TITLE, msg=self.title_prefix + self._format_title_string(self.oldUserInput['Title']), counter='')
        if self.success_in_check_playlist is not None:
            self.success_in_check_playlist()
        else:
            logger.error('1008 self.success_in_check_playlist is None')

    def toggleMute(self):
        ''' mute / unmute player '''

        if not self.paused:
            if self.PLAYER_NAME == 'mpv':
                self.muted = bool(self._mute())
            elif self.PLAYER_NAME == 'vlc':
                self._mute()
            else:
                self.muted = not self.muted
                self._mute()
            if self.muted:
                self._stop_delay_thread()
                self.title_prefix = M_STRINGS['muted']
                self.show_volume = False
            else:
                self.title_prefix = ''
                self.show_volume = True
            # logger.info('\n\nself.muted = {}\n\n'.format(self.muted))
            if self.oldUserInput['Title'] == '':
                self.outputStream.write(msg_id=STATES.TITLE, msg=self.title_prefix + self._format_title_string(self.oldUserInput['Input']), counter='')
            else:
                self.outputStream.write(msg_id=STATES.TITLE, msg=self.title_prefix + self._format_title_string(self.oldUserInput['Title']), counter='')
            if self.success_in_check_playlist is not None:
                self.success_in_check_playlist()
            else:
                logger.error('1008 self.success_in_check_playlist is None')
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('Cannot toggle mute, player paused!')

    def _mute(self):
        ''' to be implemented on subclasses '''
        pass

    def _stop(self, player_disappeared):
        pass

    def get_volume(self):
        ''' get volume, if player can report it '''
        pass

    def volumeUp(self):
        ''' increase volume '''
        if self.muted is not True:
            self._volume_up()

    def _volume_up(self):
        ''' to be implemented on subclasses '''
        pass

    def volumeDown(self):
        ''' decrease volume '''
        if self.muted is not True:
            self._volume_down()

    def _volume_down(self):
        ''' to be implemented on subclasses '''
        pass

    def _no_mute_on_stop_playback(self, player_disappeared=False):
        ''' make sure player does not stop muted, i.e. volume=0

            Currently implemented for vlc only.'''
        pass

    def _is_accepted_input(self, input_string):
        ''' subclasses are able to reject input messages
            thus limiting message procesing.
            By default, all messages are accepted.

            Currently implemented for vlc only.'''
        return True

class MpvPlayer(Player):
    '''Implementation of Player object for MPV'''

    PLAYER_DISPLAY_NAME = 'MPV'
    PLAYER_NAME = 'mpv'
    PLAYER_CMD = 'mpv'
    WIN = False
    if platform.startswith('win'):
        WIN = True
    if WIN:
        PLAYER_CMD = find_mpv_on_windows()
    NEW_PROFILE_STRING = 'volume=50\n\n'

    if pywhich(PLAYER_CMD):
        executable_found = True
    else:
        executable_found = False

    if executable_found:
        ''' items of this tuple are considered icy-title
            and get displayed after first icy-title is received '''
        icy_tokens = ('icy-title: ', 'Title: ')

        icy_audio_tokens = {}

        ''' USE_PROFILE
            -1 : not checked yet
             0 : do not use
             1 : use profile
         '''
        USE_PROFILE = -1

        ''' True if profile comes from ~/.config/mpv/mpv.conf '''
        PROFILE_FROM_USER = False

        ''' String to denote volume change '''
        volume_string = 'Volume: '
        if platform.startswith('win'):
            mpvsocket = r'\\.\pipe\mpvsocket.{}'.format(os.getpid())
        else:
            mpvsocket = '/tmp/mpvsocket.{}'.format(os.getpid())
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'mpv socket is "{mpvsocket}"')
        if os.path.exists(mpvsocket):
            os.system('rm ' + mpvsocket + ' 2>/dev/null')

        max_vol = 130

        commands = {
                'volume_up':   b'{ "command": ["cycle", "volume", "up"], "request_id": 1000 }\n',
                'volume_down': b'{ "command": ["cycle", "volume", "down"], "request_id": 1001 }\n',
                'mute':        b'{ "command": ["cycle", "mute"], "request_id": 1002 }\n',
                'pause':       b'{ "command": ["cycle", "pause"], "request_id": 1003 }\n',
                'quit':        b'{ "command": ["quit"], "request_id": 1004}\n',
                }

        ''' if found in built options, buffering is ON '''
        buffering_tokens = ('cache', 'demuxer-readahead-secs')

    def __init__(self,
                 config,
                 outputStream,
                 playback_timeout_counter,
                 playback_timeout_handler,
                 info_display_handler,
                 history_add_function,
                 recording_lock):
        config.PLAYER_NAME = 'mpv'
        super(MpvPlayer, self).__init__(
            config,
            outputStream,
            playback_timeout_counter,
            playback_timeout_handler,
            info_display_handler,
            history_add_function,
            recording_lock
        )
        self.config_files = self.all_config_files['mpv']
        # logger.error('\n\nself.config_files = {}\n\n'.format(self.config_files))
        self.recording_filename = ''
        # logger.error('\n\nMPV recording = {}\n\n'.format(self._recording))
        self._request_mpv_info_data_counter = 0

    def save_volume(self):
        ''' Saving Volume in Windows does not work;
            Profiles not supported... '''
        if int(self.volume) > 999:
            self.volume = -2
        return self._do_save_volume(self.profile_token + '\nvolume={}\n')

    def _buildStartOpts(self, a_station, playList=False):
        profiles = self._cnf.profile_manager.profiles(self.PLAYER_NAME)
        logger.error('\n\nprofiles = %s\n\n', profiles)
        all_profiles = self._cnf.profile_manager.all_profiles()
        logger.error('\n\nall_profiles = %s\n\n', all_profiles)
        ''' Builds the options to pass to mpv subprocess.'''
        # logger.error('\n\nself._recording = {}'.format(self._recording))
        # logger.error('self.profile_name = "{}"'.format(self.profile_name))

        ''' Test for newer MPV versions as it supports different IPC flags. '''
        p = subprocess.Popen([self.PLAYER_CMD, '--no-video',  '--input-ipc-server=' + self.mpvsocket], stdout=subprocess.PIPE, stdin=subprocess.PIPE, shell=False)
        if self._cnf.USE_EXTERNAL_PLAYER:
            self.recording = self.NO_RECORDING
        out = p.communicate()
        if 'not found' not in str(out[0]):
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('--input-ipc-server is supported.')
            newerMpv = True
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('--input-ipc-server is not supported.')
            newerMpv = False
        logger.error(f'{self._cnf.user_agent_string = }')
        if self._cnf.USE_EXTERNAL_PLAYER:
            opts = [self.PLAYER_CMD, '--no-video']
        else:
            opts = [self.PLAYER_CMD, '--no-video', '--quiet']
        if self.buffering_data:
            if self._cnf.buffering_enabled:
                opts.extend(self.buffering_data)
        elif self._cnf.buffering_data:
            if self._cnf.buffering_enabled:
                opts.extend(self._cnf.buffering_data)

        ''' this will set the profile too '''
        params = self.params[self.params[0]]
        # logger.error('\n\n')
        # logger.info('params = {}'.format(params))
        # logger.info('self.params = {}'.format(self.params))
        # logger.error('\n\n')
        if not params.startswith('profile:'):
            sp = params.split(' ')
            for n in sp:
                opts.append(n)

        ''' Do I have user profile in config?
            If so, can I use it?
        '''
        if not self._cnf.check_playlist:
            self.USE_PROFILE, profile = self._configHasProfile(
                a_station[Station.profile] if a_station[Station.profile] else self.profile_name
            )

        if self._recording == self.RECORD_WITH_SILENCE or \
                self._cnf.check_playlist:
            self._cnf.profile_manager.write_silenced_profile(self.PLAYER_NAME)
            opts.append('--profile=silent')
        else:
            if self.USE_PROFILE == 1:
                profile_string = None
                if self.station_volume != -1 and self.enable_per_station_volume:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f'Initial profile: "[{profile}]"')
                    ret = self._cnf.profile_manager.copy_profile_with_new_volume(
                        self.PLAYER_NAME, profile, 'pyradio-volume', str(self.station_volume)
                    )
                    if ret:
                        profile = ret
                        profile_string = f'Using profile: "[{profile}]", volume: {self.station_volume}'
                opts.append('--profile=' + profile)
                if (logger.isEnabledFor(logging.INFO)):
                    if profile_string:
                        logger.info(profile_string)
                    else:
                        logger.info(f'Using profile: "[{profile}]"')
            else:
                if (logger.isEnabledFor(logging.INFO)):
                    if self.USE_PROFILE == 0:
                        logger.info(f'Profile "[{profile}]" not found in config file!!!')
                    else:
                        logger.info('No usable profile found')

        # logger.error('\n\nself._recording = {}'.format(self._recording))
        if self._recording > 0:
            self.recording_filename = self.get_recording_filename(self.name, '.mkv')
            opts.append('--stream-record=' + self.recording_filename)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'---=== Starting Recording: "{self.recording_filename}" ===---')

        referer, referer_file = self._get_referer(
            a_station[Station.name], a_station[Station.referer]
        )
        if referer is not None:
            opts.append(r'--http-header-fields="User-Agent: ' + self._cnf.user_agent_string + r',Referer:' + referer + '"')

        if playList:
            if newerMpv:
                if not self._cnf.USE_EXTERNAL_PLAYER:
                    opts.append('--input-ipc-server=' + self.mpvsocket)
                opts.append('--playlist=' + self._url_to_use(a_station[Station.url], a_station[Station.http]))
            else:
                if not self._cnf.USE_EXTERNAL_PLAYER:
                    opts.append('--input-unix-socket=' + self.mpvsocket)
                opts.append('--playlist=' + self._url_to_use(a_station[Station.url], a_station[Station.http]))
        else:
            if newerMpv:
                if not self._cnf.USE_EXTERNAL_PLAYER:
                    opts.append('--input-ipc-server=' + self.mpvsocket)
                opts.append(self._url_to_use(a_station[Station.url], a_station[Station.http]))
            else:
                if not self._cnf.USE_EXTERNAL_PLAYER:
                    opts.append('--input-unix-socket=' + self.mpvsocket)
                opts.append(self._url_to_use(a_station[Station.url], a_station[Station.http]))

        # if self._cnf.USE_EXTERNAL_PLAYER:
        #     # opts.append('--msg-color=yes')
        #     opts.append('--msg-color=no')
        #     opts.append('--msg-level=all=trace,lavf=no,ao/pipewire=no')

        ''' check if buffering '''
        self.buffering = self._player_is_buffering(opts, self.buffering_tokens)
        with self.buffering_lock:
            self.buffering_change_function()
        # logger.error('==== self.buffering = {}'.format(self.buffering))

        logger.error(f'Opts:\n{opts}')
        return opts, None, referer, referer_file

    def _fix_returned_data(self, data):
        if isinstance(data, tuple):
            if 'int' in str(type(data[0])):
                a_data = data[1]
            else:
                a_data = data[0]
        else:
            a_data = data
        return a_data

    def _pause(self):
        ''' pause mpv '''
        ret = self._send_mpv_command('pause')
        while not ret:
            ret = self._send_mpv_command('pause')
        return self._get_pause_status()

    def _get_pause_status(self):
        while True:
            sock = self._connect_to_socket(self.mpvsocket)
            try:
                if platform.startswith('win'):
                    win32file.WriteFile(sock, b'{ "command": ["get_property", "pause"], "request_id": 600 }\n')
                else:
                    sock.sendall(b'{ "command": ["get_property", "pause"], "request_id": 600 }\n')
            except:
                self._close_pipe(sock)
                return
            # wait for response

            try:
                if platform.startswith('win'):
                    try:
                        data = win32file.ReadFile(sock, 64*1024)
                    except pywintypes.error:
                        data = b''
                else:
                    data = sock.recvmsg(4096)
                a_data = self._fix_returned_data(data)
                # logger.error('DE Received: "{!r}"'.format(a_data))

                if a_data:
                    all_data = a_data.split(b'\n')
                    for n in all_data:
                        try:
                            d = json.loads(n)
                            if d['error'] == 'success':
                                if isinstance(d['data'], bool):
                                    self._close_pipe(sock)
                                    return d['data']
                        except:
                            pass
            finally:
                pass
            self._close_pipe(sock)

    def _mute(self):
        ''' mute mpv '''
        ret = self._send_mpv_command('mute')
        while not ret:
            ret = self._send_mpv_command('mute')
        return self._get_mute_status()

    def _get_mute_status(self):
        while True:
            sock = self._connect_to_socket(self.mpvsocket)
            try:
                if platform.startswith('win'):
                    win32file.WriteFile(sock, b'{ "command": ["get_property", "mute"], "request_id": 600 }\n')
                else:
                    sock.sendall(b'{ "command": ["get_property", "mute"], "request_id": 600 }\n')
            except:
                self._close_pipe(sock)
                return
            # wait for response

            try:
                if platform.startswith('win'):
                    try:
                        data = win32file.ReadFile(sock, 64*1024)
                    except pywintypes.error:
                        data = b''
                else:
                    data = sock.recvmsg(4096)
                a_data = self._fix_returned_data(data)
                # logger.error('DE Received: "{!r}"'.format(a_data))

                if a_data:
                    all_data = a_data.split(b'\n')
                    for n in all_data:
                        try:
                            d = json.loads(n)
                            if d['error'] == 'success':
                                if isinstance(d['data'], bool):
                                    self._close_pipe(sock)
                                    return d['data']
                        except:
                            pass
            finally:
                pass
            self._close_pipe(sock)

    def _stop(self, player_disappeared):
        self.currently_recording = False
        ''' kill mpv instance '''
        self.stop_mpv_status_update_thread = True
        if not player_disappeared:
            self._send_mpv_command('quit')
        if not platform.startswith('win'):
            os.system('rm ' + self.mpvsocket + ' 2>/dev/null')
        self._icy_data = {}
        self.monitor = self.monitor_process = self.monitor_opts = None
        if self._chapters:
            self._chapters.write_chapters_to_file(self.recording_filename)

    def _volume_up(self):
        ''' increase mpv's volume '''
        self.get_volume()
        if self.volume < self.max_vol:
            self._send_mpv_command('volume_up')
        self._display_mpv_volume_value()

    def _volume_down(self):
        ''' decrease mpv's volume '''
        self.get_volume()
        if self.volume > 0:
            self._send_mpv_command('volume_down')
        self._display_mpv_volume_value()

    def _format_title_string(self, title_string):
        ''' format mpv's title '''
        return self._title_string_format_text_tag(title_string.replace(self.icy_tokens[0], self.icy_title_prefix))

    def _format_volume_string(self, volume_string):
        ''' format mpv's volume '''
        return '[' + volume_string[volume_string.find(self.volume_string):].replace('ume', '')+'] '

    def _connect_to_socket(self, server_address):
        if platform.startswith('win'):
            # logger.error('\n\n_connect_to_socket: {}\n\n'.format(server_address))
            try:
                handle = win32file.CreateFile(
                    server_address,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None
                )
                win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE, None, None)
                return handle
            except pywintypes.error:
                return None
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.connect(server_address)
                return sock
            except:
                self._close_pipe(sock)
                return None

    def _send_mpv_command(self, a_command, return_response=False):
        ''' Send a command to MPV

            Parameters
            =========
            a_command
                The command to send.
            return_response
                if True, return a string, otherwise
                return a boolean

            Returns
            =======
            If return_response is False (default), returns
                True, if the operation was a success or False
                if it failed.
            If return_response if True, return the response
                we get after issuing the command ('' if failed).

        '''

        #while True:
        #    sock = self._connect_to_socket(self.mpvsocket)
        #    if sock:
        #        break
        #    sleep(.25)
        sock = self._connect_to_socket(self.mpvsocket)
        if sock is None:
            if return_response:
                return ''
            else:
                return False

        # Send data
        try:
            if platform.startswith('win'):
                if a_command in self.commands:
                    win32file.WriteFile(sock, self.commands[a_command])
                else:
                    win32file.WriteFile(sock, a_command)
            else:
                if a_command in self.commands:
                    sock.sendall(self.commands[a_command])
                else:
                    sock.sendall(a_command)
        except:
            self._close_pipe(sock)
            if return_response:
                return ''
            else:
                return False
        # read the response
        if platform.startswith('win'):
            try:
                data = win32file.ReadFile(sock, 64*1024)
                # do not "specify sock.error as e" for except here
                # it will crash if random playback is on
                # use "except:" instead
                #
                # old command:
                # except pywintypes.error:
            except:
                data = b''
        else:
            try:
                data = sock.recvmsg(4096)
                # do not "specify sock.error as e" for except here
                # it will crash if random playback is on
                # use "except:" instead
                #
                # old command:
                # except sock.error as e:
            except:
                data = ''
        # logger.error('DE data = {}'.format(data))
            #sock.colse()
            #return False
        # logger.error('DE data = "{}"'.format(data))
        self._close_pipe(sock)
        if return_response:
            return data
        else:
            return True

    def get_volume(self):
        ''' Display volume for MPV '''
        vol = 0
        while True:
            sock = self._connect_to_socket(self.mpvsocket)
            if sock:
                break
            sleep(.25)

        # Send data
        message = b'{ "command": ["get_property", "volume"] }\n'
        try:
            if platform.startswith('win'):
                win32file.WriteFile(sock, message)
            else:
                sock.sendall(message)
        except:
            self._close_pipe(sock)
            return

        # wait for response
        got_it = True
        while got_it:
            try:
                if platform.startswith('win'):
                    try:
                        data = win32file.ReadFile(sock, 64*1024)
                    except pywintypes.error:
                        data = b''
                else:
                    data = sock.recvmsg(4096)

                # logger.error('DE Received: "{!r}"'.format(a_data))
                a_data = self._fix_returned_data(data)

                if a_data == b'':
                    break

                if data:

                    all_data = a_data.split(b'\n')
                    for n in all_data:
                        try:
                            d = json.loads(n)
                            if d['error'] == 'success':
                                try:
                                    vol = int(d['data'])
                                    got_it = False
                                    break
                                except:
                                    pass
                        except:
                            pass
            finally:
                pass
        self._close_pipe(sock)
        self.volume = vol

    def _display_mpv_volume_value(self):
        ''' Display volume for MPV

            Calling get_volume
        '''

        self.get_volume()
        if self.oldUserInput['Title']:
            info_string = self._format_title_string(self.oldUserInput['Title'])
        else:
            info_string = self._format_title_string(self.oldUserInput['Input'])
        string_to_show = self._format_volume_string('Volume: ' + str(self.volume) + '%') + info_string
        self.outputStream.write(msg_id=STATES.VOLUME, msg=string_to_show, counter='')
        self.threadUpdateTitle()

class MpPlayer(Player):
    '''Implementation of Player object for MPlayer'''

    PLAYER_DISPLAY_NAME = 'MPlayer'
    PLAYER_NAME = 'mplayer'
    PLAYER_CMD = 'mplayer'
    WIN = False
    if platform.startswith('win'):
        WIN = True
    if WIN:
        PLAYER_CMD = find_mplayer_on_windows()
    NEW_PROFILE_STRING = 'softvol=1\nsoftvol-max=300\nvolstep=1\nvolume=50\n\n'
    if pywhich(PLAYER_CMD):
        executable_found = True
    else:
        executable_found = False

    if executable_found:
        ''' items of this tuple are considered icy-title
            and get displayed after first icy-title is received
        '''
        icy_tokens = ('ICY Info:', 'Metadata update for StreamTitle: ')

        # 'audio-data' comes from playback start
        icy_audio_tokens = {
                'Name   : ': 'icy-name',
                'Genre  : ': 'icy-genre',
                'Website: ': 'icy-url',
                'Bitrate: ': 'icy-br',
                'Opening audio decoder: ': 'codec',
                }


        ''' USE_PROFILE
            -1 : not checked yet
             0 : do not use
             1 : use profile
        '''
        USE_PROFILE = -1

        ''' True if profile comes from ~/.mplayer/config '''
        PROFILE_FROM_USER = False

        ''' String to denote volume change '''
        volume_string = 'Volume: '

        ''' if found in built options, buffering is ON '''
        buffering_tokens = ('cache', )

    def __init__(self,
                 config,
                 outputStream,
                 playback_timeout_counter,
                 playback_timeout_handler,
                 info_display_handler,
                 history_add_function,
                 recording_lock):
        config.PLAYER_NAME = 'mplayer'
        super(MpPlayer, self).__init__(
            config,
            outputStream,
            playback_timeout_counter,
            playback_timeout_handler,
            info_display_handler,
            history_add_function,
            recording_lock
        )
        self.volume = -1
        self._detected_icon_url = None
        self._thrededreq_thread = None
        self._vlc_url = None
        self.config_files = self.all_config_files['mplayer']
        if platform.startswith('win') and \
                int(platform_uname().release) < 10:
            ''' Existing mplayer Windows 7 and earlier
                implementations do not support profiles
            '''
            self._mplayer_on_windows7 = True

    def save_volume(self):
        if platform.startswith('win'):
            return self._do_save_volume('volume={}\r\n')
            return 0
        return self._do_save_volume(self.profile_token + '\nvolstep=1\nvolume={}\n')

    def _calculate_buffer_size_in_kb(self, delay_seconds, bitrate_kbps=None):
        ''' return delay in KB for mplayer '''
        if bitrate_kbps is None:
            bitrate_kbps = 128
        if isinstance(delay_seconds, str) and \
                '@' in delay_seconds:
            sp = delay_seconds.split('@')
            delay_seconds = sp[0]
            bitrate_kbps = sp[1]
        try:
            delay_seconds = int(delay_seconds)
        except ValueError:
            delay_seconds = 20
        try:
            bitrate_kbps = int(bitrate_kbps)
        except ValueError:
            bitrate_kbps = 128
        # Convert bitrate from kbps to bytes per second
        bytes_per_second = (bitrate_kbps * 1000) / 8

        # Calculate buffer size in bytes
        buffer_size_bytes = bytes_per_second * delay_seconds

        # Convert buffer size to kilobytes
        buffer_size_kb = int( buffer_size_bytes / 1024 )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'using {buffer_size_kb}KB for a delay of {delay_seconds}, seconds (bitrate: {bitrate_kbps}kbps)')

        return buffer_size_kb

    def _calculate_kb_to_seconds(self, kb, bitrate=None):
        if bitrate is None:
            bitrate = 128

        # Convert bitrate from kbps to bytes per second
        bytes_per_second = (bitrate * 1000) / 8

        # Convert kilobytes to bytes
        bytes_total = kb * 1024

        # Calculate the time in seconds
        seconds = bytes_total / bytes_per_second

        # Round up to the nearest integer
        return math.ceil(seconds)

    def _buildStartOpts(self, a_station, playList=False):
        ''' Builds the options to pass to mplayer subprocess.'''
        if self._cnf.USE_EXTERNAL_PLAYER:
            self.recording = self.NO_RECORDING
        opts = [self.PLAYER_CMD, '-vo', 'null', '-msglevel', 'all=6']
        if self.buffering_data:
            if self._cnf.buffering_enabled:
                opts.extend(self.buffering_data)
        elif self._cnf.buffering_data:
            if self._cnf.buffering_enabled:
                if int(self._cnf.buffering_data[1]) < 61:
                    x = self._calculate_buffer_size_in_kb(int(self._cnf.buffering_data[1]))
                    self._cnf.buffering_data[1] = str(x)
                opts.extend(self._cnf.buffering_data)
        # opts = [self.PLAYER_CMD, '-vo', 'null']
        monitor_opts = None

        referer, referer_file = self._get_referer(
            a_station[Station.name], a_station[Station.referer]
        )
        if referer is not None:
            opts.append(r'-http-header-fields')
            opts.append(r'Referer: "' + referer + '"')

        ''' Do I have user profile in config?
            If so, can I use it?
        '''
        if not self._cnf.check_playlist:
            self.USE_PROFILE, profile = self._configHasProfile(
                a_station[Station.profile] if a_station[Station.profile] else self.profile_name
            )

        if self._cnf.check_playlist:
            self._cnf.profile_manager.write_silenced_profile(self.PLAYER_NAME)
            opts.append('-profile')
            opts.append('silent')
        elif self._recording == self.RECORD_WITH_SILENCE:
            if self.USE_PROFILE > -1:
                self._cnf.profile_manager.write_silenced_profile(self.PLAYER_NAME)
                opts.append('-profile')
                opts.append('silent')
            else:
                self._recording = self.RECORD_AND_LISTEN
        else:
            if self.USE_PROFILE == 1:
                profile_string = None
                if self.station_volume != -1 and self.enable_per_station_volume:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f'Initial profile: "[{profile}]"')
                    ret = self._cnf.profile_manager.copy_profile_with_new_volume(
                        self.PLAYER_NAME, profile, 'pyradio-volume', str(self.station_volume)
                    )
                    if ret:
                        profile = ret
                        profile_string = f'Using profile: "[{profile}]", volume: {self.station_volume}'
                opts.append('-profile')
                opts.append(profile)
                if (logger.isEnabledFor(logging.INFO)):
                    if profile_string:
                        logger.info(profile_string)
                    else:
                        logger.info(f'Using profile: "[{profile}]"')
            else:
                if (logger.isEnabledFor(logging.INFO)):
                    if self.USE_PROFILE == 0:
                        logger.info(f'Profile "[{profile}]" not found in config file!!!')
                    else:
                        logger.info('No usable profile found')

        ''' this will set the profile too '''
        params = self.params[self.params[0]]
        # logger.error('\n\n')
        # logger.info('params = {}'.format(params))
        # logger.info('self.params = {}'.format(self.params))
        # logger.error('\n\n')
        if not params.startswith('profile:'):
            sp = params.split(' ')
            for n in sp:
                opts.append(n)

        # logger.error('\n\nself._recording = {}'.format(self._recording))
        if self._recording > 0:
            monitor_opts = opts[:]
            if self._recording == self.RECORD_WITH_SILENCE:
                try:
                    i = [y for y, x in enumerate(opts) if x == '-profile'][0]
                    opts[i+1] = 'silent'
                except IndexError:
                    opts.append('-profile')
                    opts.append('silent')
            try:
                ''' find and remove -playlist url '''
                i = [y for y, x in enumerate(monitor_opts) if x == '-playlist'][0]
                del monitor_opts[i+1]
                del monitor_opts[i]
            except IndexError:
                ''' not -playlist, find and remove url '''
                try:
                    i = [y for y, x in enumerate(monitor_opts) if x == a_station[Station.url]][0]
                    del monitor_opts[i]
                except IndexError:
                    pass
            self.recording_filename = self.get_recording_filename(self.name, '.mkv')
            monitor_opts.append(self.recording_filename)
            opts.append('-dumpstream')
            opts.append('-dumpfile')
            opts.append(self.recording_filename)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'---=== Starting Recording: "{self.recording_filename}" ===---')

        ''' check if buffering '''
        self.buffering = self._player_is_buffering(opts, self.buffering_tokens)
        with self.buffering_lock:
            self.buffering_change_function()
        # logger.error('---- self.buffering = {}'.format(self.buffering))

        if not self.buffering:
            opts.remove('-msglevel')
            opts.remove('all=6')

        ''' add URL '''
        if playList:
            opts.append('-playlist')
        opts.append(self._url_to_use(a_station[Station.url], a_station[Station.http]))

        # logger.error('Opts:\n{0}\n{1}'.format(opts, monitor_opts))
        return opts, monitor_opts, referer, referer_file

    def _mute(self):
        ''' mute mplayer '''
        self._sendCommand('m')

    def _pause(self):
        ''' pause streaming (if possible) '''
        self._sendCommand('p')

    def pause(self):
        ''' pause streaming (if possible) '''
        self._sendCommand('p')

    def _stop(self, player_disappeared):
        self.currently_recording = False
        ''' kill mplayer instance '''
        self.stop_mpv_status_update_thread = True
        if not player_disappeared:
            self._sendCommand('q')
        self._icy_data = {}
        self.monitor = self.monitor_process = self.monitor_opts = None
        if self._chapters:
            self._chapters.write_chapters_to_file(self.recording_filename)

    def _volume_up(self):
        ''' increase mplayer's volume '''
        self._sendCommand('*')

    def _volume_down(self):
        ''' decrease mplayer's volume '''
        self._sendCommand('/')

    def get_volume(self):
        ''' get mplayer's actual_volume'''
        if int(self.volume) < 0:
            self.show_volume = False
            count = 0
            self._volume_down()
            sleep(.1)
            old_vol = self.volume
            self._volume_up()
            while self.volume == old_vol:
                sleep(.1)
                count += 1
                if count > 4:
                    break
            self.show_volume = True

    def _format_title_string(self, title_string):
        ''' format mplayer's title '''
        if "StreamTitle='" in title_string:
            tmp = title_string[title_string.find("StreamTitle='"):].replace("StreamTitle='", self.icy_title_prefix)
            ret_string = tmp[:tmp.find("';")]
        else:
            ret_string = title_string

        if logger.isEnabledFor(logging.DEBUG):
            ''' detect icon url in StreamUrl '''
            if 'StreamUrl=' in title_string:
                splitted = title_string.split(';')
                logger.error(title_string.split(';'))
                for i in (-1, -2):
                    if 'StreamUrl=' in splitted[i]:
                        icon_url = splitted[i].replace('StreamUrl=', '').replace("'", "")
                        logger.error(f'{icon_url = }')
                        if icon_url.endswith('.jpg') or icon_url.endswith('.png'):
                            self._detected_icon_url = icon_url
                            logger.error('found!!!')
                            # logger.critical('    icon: {}'.format(self._detected_icon_url))
                        break
            else:
                self._detected_icon_url = None

        if '"artist":"' in ret_string:
            ''' work on format:
                ICY Info: START_SONG='{"artist":"Clelia Cafiero","title":"M. Mussorgsky-Quadri di un'esposizione"}';
                Fund on "ClassicaViva Web Radio: Classical"
            '''
            ret_string = self.icy_title_prefix + ret_string[ret_string.find('"artist":')+10:].replace('","title":"', ' - ').replace('"}\';', '')
        return self._title_string_format_text_tag(ret_string)

    def _format_volume_string(self, volume_string):
        ''' format mplayer's volume '''
        return '[' + volume_string[volume_string.find(self.volume_string):].replace(' %','%').replace('ume', '')+'] '


class VlcPlayer(Player):
    '''Implementation of Player for VLC'''
    PLAYER_DISPLAY_NAME = 'VLC'
    PLAYER_NAME = 'vlc'
    WIN = False
    if platform.startswith('win'):
        WIN = True
    if WIN:
        # TODO: search and find vlc.exe
        # PLAYER_CMD = "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
        PLAYER_CMD = find_vlc_on_windows()
        if PLAYER_CMD:
            executable_found = True
        else:
            executable_found = False
    else:
        PLAYER_CMD = "cvlc"
        if pywhich(PLAYER_CMD):
            executable_found = True
        else:
            executable_found = False

    if executable_found:
        ''' items of this tuple are considered icy-title
            and get displayed after first icy-title is received '''
        icy_tokens = ('New Icy-Title=', )

        icy_audio_tokens = {
                'Icy-Name:': 'icy-name',
                'Icy-Genre:': 'icy-genre',
                'icy-name:': 'icy-name',
                'icy-genre:': 'icy-genre',
                'icy-url:': 'icy-url',
                'icy-br:': 'icy-br',
                'format:': 'audio_format',
                'using audio decoder module ': 'codec-name',
                }

        muted = paused = False

        ''' String to denote volume change '''
        volume_string = '( audio volume: '

        ''' vlc reports volume in values 0..256 '''
        actual_volume = -1
        max_volume = 256

        ''' When found in station transmission, playback is on '''
        if platform.startswith('win'):
            _playback_token_tuple = (
                # ' successfully opened',
                # 'main audio ',
                # 'Content-Type: audio',
                ' Segment #',
                'using audio decoder module',
                'answer code 200',
                ' buffering done',
                'Buffering '
            )
            # max_volume = 1000
        else:
            _playback_token_tuple = (
                # 'Content-Type: audio',
                ' Segment #',
                'using audio filter module',
                'using audio decoder module',
                'answer code 200',
                ' buffering done'
            )

        ''' Windows only variables '''
        _vlc_stdout_log_file = ''
        _port = None
        win_show_vlc_volume_function = None

        ''' if found in built options, buffering is ON '''
        buffering_tokens = ('--network-caching', )

    def __init__(self,
                 config,
                 outputStream,
                 playback_timeout_counter,
                 playback_timeout_handler,
                 info_display_handler,
                 history_add_function,
                 recording_lock):
        config.PLAYER_NAME = 'vlc'
        super(VlcPlayer, self).__init__(
            config,
            outputStream,
            playback_timeout_counter,
            playback_timeout_handler,
            info_display_handler,
            history_add_function,
            recording_lock
        )
        # self.config_files = self.all_config_files['vlc']
        self._thrededreq_thread = None
        self._vlc_url = None
        self._unmuted_volume = -1
        self._config_volume = -1
        self._read_config()
        self.config_files = self.all_config_files['vlc']

    def _on_connect(self):
        logger.error('\n\n***********  VLC on connect\n\n')
        if self.buffering:
            logger.error('not setting volume: buffering')
        if self._config_volume > -1:
            self.get_volume()
            #self.actual_volume = int(self.max_volume*self._config_volume/100)
            #logger.info('1 self.actual_volume = {}'.format(self.actual_volume))
            volume_to_use = self.station_volume
            if volume_to_use == -1:
                volume_to_use = self._config_volume
            if self.volume != volume_to_use:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('volume: [config, station, used] = [{}, {}, {}]'.format(
                        self._config_volume, self.station_volume, volume_to_use)
                                 )
                #self.volume = self._config_volume
                #self.set_volume(self.actual_volume)
                self.set_volume(volume_to_use)

    def _read_config(self):
        if self._config_volume == -1:
            try:
                with open(self.all_config_files['vlc'][0], 'r', encoding='utf-8') as f:
                    val = f.read().strip()
            except:
                # logger.error('\n\nself._config_volume = {}\n\n'.format(self._config_volume))
                return
            try:
                self._config_volume = int(val)
            except ValueError:
                pass
            # logger.error('\n\nself._config_volume = {}\n\n'.format(self._config_volume))

    def _write_config(self):
        # logger.error('\n\nself.volume = {}'.format(self.volume))
        # logger.error('self.actual_volume = {}'.format(self.actual_volume))
        # ovol = round(int(self.volume)*100/self.max_volume)
        # logger.error('ovol = {}\n\n'.format(ovol))
        try:
            with open(self.all_config_files['vlc'][0], 'w', encoding='utf-8') as f:
                # f.write(str(ovol))
                f.write(str(self.volume))
        except:
            return False
        self._config_volume = self.volume
        return True

    def _volume_set(self, vol):
        ''' increase vlc's volume '''
        if self.WIN:
            self._win_volup()
            self._win_show_vlc_volume()
        else:
            self._sendCommand(f'volume {vol}\n')

    def set_volume(self, vol):
        if self.isPlaying() and \
                not self.muted:
            self.get_volume()
            ivol = int(vol)
            ovol = round(self.max_volume*ivol/100)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'setting volume at {ivol}% ({ovol}) with max_volume={self.max_volume}')
            if ovol != int(self.volume):
                diff = 10 if ovol > int(self.volume) else -10
                vols = [x + diff for x in range(int(self.volume), ovol, diff)]
                vols[-1] = ovol
                if self.WIN:
                    self.show_volume = False
                    for a_vol in vols:
                        self._thrededreq(f'volume {a_vol}')
                        self.volume = a_vol
                        sleep(.01)
                    self._win_get_volume()
                    self.show_volume = True
                    self._win_show_vlc_volume()
                else:
                    self.show_volume = False
                    for a_vol in vols:
                        self._sendCommand(f'volume {a_vol}\n')
                        self.volume = a_vol
                        sleep(.01)
                    self.show_volume = True
                    self._sendCommand('status\n')

    def save_volume(self):
        return self._do_save_volume('{}')

    def _buildStartOpts(self, a_station, playList=False):
        ''' Builds the options to pass to vlc subprocess.'''
        monitor_opts = None
        self._vlc_url = self._url_to_use(a_station[Station.url], a_station[Station.http])
        if self._cnf.USE_EXTERNAL_PLAYER:
            self.recording = self.NO_RECORDING
        if self.WIN:
            ''' Get a random port (44000-44999)
                Create a log file for vlc and make sure it is unique
                and it is created beforehand
            '''
            random.seed()
            ok_to_go_on = False
            while True:
                logger.error(f'DE getting port for {self.config_dir}')
                self._port = random.randint(44000, 44999)
                self._vlc_stdout_log_file = os.path.join(self.config_dir, 'vlc_log.' + str(self._port))
                if os.path.exists(self._vlc_stdout_log_file):
                    ''' another instance running? '''
                    logger.error(f'DE file exists: "{self._vlc_stdout_log_file}"')
                    continue
                try:
                    with open(self._vlc_stdout_log_file, 'w', encoding='utf-8'):
                        ok_to_go_on = True
                except:
                    logger.error(f'DE file not opened: "{self._vlc_stdout_log_file}"')
                    continue
                if ok_to_go_on:
                    break

            if self._cnf.USE_EXTERNAL_PLAYER:
                opts = [self.PLAYER_CMD, '--no-video', '--no-one-instance', '-Irc',
                    self._url_to_use(a_station[Station.url], a_station[Station.http])]
            else:
                opts = [self.PLAYER_CMD, '--no-video', '--no-one-instance',
                    '--no-volume-save', '-Irc', '--rc-host', '127.0.0.1:' + str(self._port),
                    '--file-logging', '--logmode', 'text', '--log-verbose', '3',
                    '--logfile', self._vlc_stdout_log_file, '-vv',
                    self._url_to_use(a_station[Station.url], a_station[Station.http])]

                if logger.isEnabledFor(logging.INFO):
                    logger.info(f'vlc listening on 127.0.0.1:{self._port}')
                    logger.info(f'vlc log file: "{self._vlc_stdout_log_file}"')

        else:
            if self.recording == self.NO_RECORDING:
                if self.WIN:
                    opts = [self.PLAYER_CMD, '--no-video', '--no-one-instance',
                            '--no-volume-save', '-Irc', '-vv', self._vlc_url]
                else:
                    opts = [self.PLAYER_CMD, '--no-video', '--no-one-instance',
                            '--no-volume-save', '-Irc', '-vv']
                if self._cnf.USE_EXTERNAL_PLAYER:
                    opts.pop(opts.index('-vv'))
            else:
                if self.WIN:
                    opts = [self.PLAYER_CMD, '--no-video', '--no-one-instance',
                            '--no-volume-save', '-Irc', '-vv', self._vlc_url]
                else:
                    opts = [self.PLAYER_CMD, '--no-video', '--no-one-instance',
                            '--no-volume-save', '-Irc', '-vv']

        if platform.lower().startswith('dar'):
            # MacOS VLC does not support --no-one-instance
            opts.pop(1)

        if self.buffering_data:
            if self._cnf.buffering_enabled:
                opts.extend(self.buffering_data)
        elif self._cnf.buffering_data:
            if self._cnf.buffering_enabled:
                opts.extend(self._cnf.buffering_data)

        referer, referer_file = self._get_referer(
            a_station[Station.name], a_station[Station.referer]
        )
        if referer is not None:
            opts.append('--http-user-agent')
            opts.append(self._cnf.user_agent_string)
            opts.append(r'--http-referrer')
            opts.append(referer)

        ''' this will set the profile too '''
        if self.params[0] > 1:
            params = self.params[self.params[0]]
            # logger.error('\n\n')
            # logger.info('params = {}'.format(params))
            # logger.info('self.params = {}'.format(self.params))
            # logger.error('\n\n')
            if not params.startswith('profile:'):
                sp = params.split(' ')
                for n in sp:
                    opts.append(n)

        # logger.error('\n\nself._recording = {}'.format(self._recording))
        if self._recording > 0:
            monitor_opts = opts[:]
            try:
                i = [y for y, x in enumerate(monitor_opts) if x == a_station[Station.url]][0]
                del monitor_opts[i]
            except IndexError:
                pass
            self.recording_filename = self.get_recording_filename(self.name, '.mkv')
            opts.append('--sout')
            opts.append(r'file/ps:' + self.recording_filename)
            monitor_opts.append(self.recording_filename)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'---=== Starting Recording: "{self.recording_filename}" ===---')

        ''' check if buffering '''
        self.buffering = self._player_is_buffering(opts, self.buffering_tokens)
        with self.buffering_lock:
            self.buffering_change_function()

        if self._cnf.USE_EXTERNAL_PLAYER:
            opts.append(a_station[Station.url])

        return opts, monitor_opts, referer, referer_file

    def _mute(self):
        ''' mute vlc '''
        # logger.error('DE vlc_mute(): muted = {}'.format(self.muted))
        if self.muted:
            if self.WIN:
                self._win_set_volume(self._unmuted_volume)
                self.volume = int(100 * self._unmuted_volume / self.max_volume)
            else:
                self._sendCommand(f'volume {self.actual_volume}\n')
                self.volume = int(100 * self.actual_volume / self.max_volume)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'VLC unmuted: {self.actual_volume} ({self.volume}%)')
            self.muted = False
        else:
            if self.actual_volume == -1:
                self.get_volume()
            if self.WIN:
                self._win_mute()
            else:
                self._sendCommand('volume 0\n')
            self.muted = True
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('VLC muted: 0 (0%)')

    def _pause(self):
        ''' pause streaming (if possible) '''
        if self.WIN:
            self._win_pause()
        else:
            self._sendCommand('pause\n')

    def pause(self):
        ''' pause streaming (if possible) '''
        if self.WIN:
            self._win_pause()
        else:
            self._sendCommand('pause\n')

    def _stop(self, player_disappeared):
        self.currently_recording = False
        ''' kill vlc instance '''
        self.stop_win_vlc_status_update_thread = True
        if logger.isEnabledFor(logging.INFO):
            logger.info('setting self.stop_win_vlc_status_update_thread = True')
        if self.ctrl_c_pressed:
            return
        if self.WIN:
            if self.process and \
                    not player_disappeared:
                logger.error('>>>> Terminating process')
                self._req('quit')
            threading.Thread(target=self._remove_vlc_stdout_log_file, args=()).start()
        else:
            if not player_disappeared:
                self._sendCommand('shutdown\n')
        self._icy_data = {}
        self.volume = -1
        self.monitor = self.monitor_process = self.monitor_opts = None
        if self._chapters:
            self._chapters.write_chapters_to_file(self.recording_filename)

    def _remove_vlc_stdout_log_file(self):
        file_to_remove = self._vlc_stdout_log_file
        if file_to_remove:
            while os.path.exists(file_to_remove):
                try:
                    os.remove(file_to_remove)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug('vlc log file removed: "' + file_to_remove + "'")
                except:
                    pass
                    # logger.error('DE Failed {}'.format(count))

    def _volume_up(self):
        ''' increase vlc's volume '''
        if self.WIN:
            self._win_volup()
            self._win_show_vlc_volume()
        else:
            self._sendCommand('volup\n')

    def _volume_down(self):
        ''' decrease vlc's volume '''
        if self.WIN:
            self._win_voldown()
            self._win_show_vlc_volume()
        else:
            self._sendCommand('voldown\n')

    def _format_volume_string(self, volume_string=None):
        ''' format vlc's volume '''
        if not self.WIN:
            dec_sep = '.' if '.' in volume_string else ','
            self.actual_volume = int(volume_string.split(self.volume_string)[1].split(dec_sep)[0].split()[0])
            self.volume = int(100 * self.actual_volume / self.max_volume)
        return '[' + M_STRINGS['vol_'] + f'{self.volume}%] '

    def _format_title_string(self, title_string):
        ''' format vlc's title '''
        sp = title_string.split(self.icy_tokens[0])
        if sp[0] == title_string:
            ret_string = title_string
        else:
            ret_string = self.icy_title_prefix + sp[1]
        return self._title_string_format_text_tag(ret_string)

    def _is_accepted_input(self, input_string):
        ''' vlc input filtering '''
        ret = False
        if self.WIN:
            ''' adding _playback_token_tuple contents here
                otherwise they may not be handled at all...
            '''
            accept_filter = (self.volume_string,
                             'buffering',
                             'error',
                             'debug: ',
                             'format: ',
                             'using: ',
                             'Content-Type',
                             'main audio',
                             'Segment #',
                             'icy-',
                             'Icy-'
                             )
        else:
            accept_filter = (self.volume_string,
                             'buffering',
                             'error',
                             'http stream debug: ',
                             'format: ',
                             ': using',
                             'icy-',
                             'Icy-',
                             )
        reject_filter = ()
        for n in accept_filter:
            if n in input_string:
                ret = True
                break
        if ret:
            for n in reject_filter:
                if n in input_string:
                    ret = False
                    break
        return ret

    def get_volume(self, repeat=False):
        ''' get vlc's actual_volume'''
        # logger.error('=======================')
        old_vol = int(self.volume)
        # logger.error('self.volume = {}'.format(self.volume))
        if old_vol <= 0:
            self.show_volume = False
            if self.WIN:
                self._win_get_volume()
            else:
                self._sendCommand('status\n')
                sleep(.1)
                count = 0
                while int(self.volume) == old_vol:
                    sleep(.1)
                    count += 1
                    if count > 4:
                        break
            self.show_volume = True
        # logger.error('self.volume = {}'.format(self.volume))
        # logger.error('repeat = {}'.format(repeat))
        if self.WIN and int(self.volume) <= 0 and not repeat:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('got volume=0, repeating after 1 second')
            sleep(1)
            self.get_volume(repeat=True)
        self.actual_volume = self.volume
        self.volume = int(100 * self.actual_volume / self.max_volume)
        # logger.error('Final')
        # logger.error('self.actual_volume = {}'.format(self.actual_volume))
        # logger.error('self.volume = {}'.format(self.volume))
        # logger.error('=======================')

    def _no_mute_on_stop_playback(self, player_disappeared=False):
        ''' make sure vlc does not stop muted '''
        if self.ctrl_c_pressed:
            return
        if self.isPlaying() and \
                not player_disappeared:
            self.show_volume = False
            self.set_volume(0)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('VLC volume set to 0 at exit')
            self.show_volume = True

    '''   WINDOWS PART '''

    def _req(self, msg, ret_function=None, full=True):
        response = ''
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Connect to server and send data
                sock.settimeout(0.7)
                sock.connect(('127.0.0.1', self._port))
                response = ''
                received = ''
                sock.sendall(bytes(msg + '\n', 'utf-8'))
                if msg != 'quit':
                    try:
                        while (True):
                            received = (sock.recv(4096)).decode()
                            response = response + received
                            if full:
                                if response.count('\r\n') > 1:
                                    sock.close()
                                    break
                            else:
                                if response.count('\r\n') > 0:
                                    sock.close()
                                    break
                    except:
                        response = response + received
                sock.close()
        except:
            pass
        # logger.info('response = "{}"'.format(response))
        if msg == 'quit':
            self.process.terminate()
            self.process = None
        if ret_function:
            ret_function(response)
        return response

    def _thrededreq(self, msg, ret_function=None):
        self._thrededreq_thread = threading.Thread(
            target=self._req,
            args=(msg,ret_function)
        )
        self._thrededreq_thread.start()
        self._thrededreq_thread.join()
        while self._thrededreq_thread.is_alive():
            sleep(.01)

    def _win_show_vlc_volume(self):
        #if self.win_show_vlc_volume_function:
        self._win_get_volume()
        self._thrededreq_thread.join()
        pvol = int(100 * self.actual_volume / self.max_volume)
        if pvol > 0:
            avol = '[' + M_STRINGS['vol_'] + f'{pvol}%] '
            if self.show_volume and self.oldUserInput['Title']:
                self.outputStream.write(msg_id=STATES.VOLUME, msg=avol + self.oldUserInput['Title'], counter='')
                self.threadUpdateTitle()

    def _win_get_volume(self):
        self._thrededreq('status', self._get_volume_response)

    def _get_volume_response(self, msg):
        # logger.debug('msg = "{}"'.format(msg))
        parts = msg.split('\r\n')
        # logger.debug('parts = {}'.format(parts))
        for n in parts:
            if 'volume' in n:
                vol = n.split(': ')[-1].replace(' )', '')
                for n in ('.', ','):
                    ind = vol.find(n)
                    if ind > -1:
                        vol = vol[:ind]
                        break
                # logger.debug('vol = "{}"'.format(vol))
                try:
                    self.actual_volume = int(vol)
                except ValueError:
                    # logger.error('DE ValueError: vol = {}'.format(vol))
                    return
                break
        # logger.debug('self.actual_volume = {}'.format(self.actual_volume))
        if self.actual_volume == 0:
            self.muted = True
            self.volume = 0
        else:
            self.muted = False
            self.volume = int(100 * self.actual_volume / self.max_volume)
        #self.print_response(vol)

    def _win_volup(self):
        self._thrededreq('volup 1')

    def _win_voldown(self):
        self._thrededreq('voldown 1')

    def _win_set_volume(self, vol):
        ivol = int(vol)
        self._thrededreq('volume ' + str(ivol))
        self.actual_volume = ivol
        self.volume = int(100 * self.actual_volume / self.max_volume)

    def _win_mute(self):
        self._win_get_volume()
        self._unmuted_volume = self.actual_volume
        self._thrededreq('volume 0')
        self.actual_volume = self.volume = 0
        self.muted = True

    def _win_pause(self):
        self._thrededreq('pause')

    def _win_is_playing(self):
        self._thrededreq('is_playing', self._win_get_playing_state)

    def _win_get_playing_state(self, msg):
        parts = msg.split('\r\n')
        for n in parts:
            if n == '1' or 'play state:' in n:
                break

class PyRadioChapters():

    HAS_MKVTOOLNIX = False

    mkvmerge = None

    _list= []
    _out = []
    _mkv_file = None
    _chapters_file = None
    _output_file = None

    def __init__(
            self,
            config,
            chapter_time,
            encoding='urf-8'
            ):
        # cover_dir is the data dir
        self._tag_file = None
        self._mkvmerge_is_done = False
        self._cnf = config
        self._playlist = os.path.basename(self._cnf.station_path)[:-4]
        self._chapters_time_function = chapter_time
        self._encoding = encoding
        self.mkvmerge = ''
        self._output_dir = self._cnf.recording_dir
        self.look_for_mkvmerge()

    def look_for_mkvmerge(self):
        if platform.lower().startswith('win'):
            s_path = (
                    r'C:\Program Files\MKVToolNix\mkvmerge.exe',
                    r'C:\Program Files (x86)\MKVToolNix\mkvmerge.exe',
                    os.path.join(self._cnf.stations_dir, 'mkvtoolnix', 'mkvmerge.exe')
                    )
            for n in s_path:
                if os.path.exists(n):
                    self.mkvmerge = n
                    self.HAS_MKVTOOLNIX = True
                    break
        else:
            p = subprocess.Popen(
                    'which mkvmerge',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                    )
            r = p.communicate()
            self.HAS_MKVTOOLNIX = True if p.returncode == 0 else False
            if self.HAS_MKVTOOLNIX:
                self.mkvmerge = r[0].decode('utf-8').strip()
            if not self.HAS_MKVTOOLNIX and platform.lower().startswith('dar'):
                mkvmerge_file = os.path.join(self._cnf.data_dir, 'mkvmerge')
                if os.path.exists(mkvmerge_file):
                    self.HAS_MKVTOOLNIX = True
                    self.mkvmerge = mkvmerge_file
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'mkvmerge is: "{self.mkvmerge}"')

    def add_function(self):
        ''' return the function to use to add
            items to the list of chapters
            Returns None if chapters not supported
        '''
        if self.HAS_MKVTOOLNIX:
            return self.add
        return None

    def add(self, a_title=None):
        if self.HAS_MKVTOOLNIX:
            if a_title is None:
                self._list = []
                self._list.append([datetime.now()])
            else:
                if self._list:
                    if self._list[-1][1] == a_title:
                        return
                # self._list.append([datetime.now(), a_title])
                try:
                    self._list.append([self._chapters_time_function(), a_title])
                except AttributeError:
                    self._list.append([datetime.now(), a_title])

    def clear(self):
        self._list = []
        self._out = []
        self._mkv_file = None
        self._chapters_file = None

    def write_chapters_to_file(self, input_file):
        if not self._mkvmerge_is_done:
            if input_file is None or input_file == '':
                if logger.isEnabledFor(logging.INFO):
                    logger.info('empty input file provided! Exiting!')
            else:
                if self.HAS_MKVTOOLNIX:
                    if logger.isEnabledFor(logging.INFO):
                        logger.info(f'starting mkvmerge!\ninput_file: "{input_file}"')
                    threading.Thread(
                            target=self.write_chapters_to_file_thread(input_file)
                        )
                else:
                    if logger.isEnabledFor(logging.INFO):
                        logger.info('mkvmerge not found!')

    def write_chapters_to_file_thread(self, input_file):
        opts = []
        self._tag_file = input_file[:-4] + '.xml'
        # remove tmp_ from begining of filename
        self._tag_file = self._remove_starting_tmp_string(self._tag_file)
        opts = [self.mkvmerge,
                '--global-tags', self._tag_file,
                ]
        self._output_file = None
        self._mkv_file = None
        if self.create_chapter_file(input_file):
            if len(self._list) > 1:
                opts.extend([
                    '--chapters', self._chapters_file,
                    ])
        if self._output_file is None:
            if logger.isEnabledFor(logging.INFO):
                logger.info('Output file is None... Quiting mkvmerge')
            return
        elif self._mkv_file is None:
            if logger.isEnabledFor(logging.INFO):
                logger.info('MKV file is None... Quiting mkvmerge')
            return
        t_dir_dir = os.path.dirname(self._tag_file)
        cover_file = None
        for n in (
                os.path.join(t_dir_dir, 'user-cover.png'), \
                os.path.join(t_dir_dir, 'cover.png'), \
                os.path.join(self._cnf.data_dir, 'user-cover.png'), \
                os.path.join(self._cnf.data_dir, 'cover.png'), \
                os.path.join(os.path.dirname(__file__), 'icons', 'cover.png')
        ):
            if os.path.exists(n):
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f'cover file is: "{n}"')
                cover_file = n
                break
        if cover_file:
            opts.extend([
                '--attachment-mime-type', 'image/png',
                '--attachment-name', 'cover',
                '--attach-file', cover_file
                ])
        opts.extend([
            '-o', self._output_file,
            self._mkv_file
            ])
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'merge options = {opts}')
        p = subprocess.Popen(
                opts, shell=False,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE
                )
        _, err = p.communicate()
        # logger.error('outs = "{0}", err = "{1}"'.format(outs, err))
        if p.returncode == 0:
            if logger.isEnabledFor(logging.INFO):
                logger.info('mkvmerge was successful!')
            self._mkvmerge_is_done = True
            for n in self._chapters_file, self._tag_file, self._mkv_file:
                try:
                    os.remove(n)
                except:
                    pass
            return True
        else:
            if logger.isEnabledFor(logging.ERROR):
                logger.error(f'mkvmerge failed with error:\n{err}')
            return False

    def _remove_starting_tmp_string(self, a_string):
        sp = a_string.split(os.sep)
        if sp[-1].startswith('tmp_'):
            sp[-1] = sp[-1][4:]
            return os.sep.join(sp)
        return a_string

    def create_chapter_file(self, input_file):
        if not input_file:
            if logger.isEnabledFor(logging.ERROR):
                logger.error('input file not found!!!')
            return False
        # logger.error('HAS_MKVTOOLNIX = {}'.format(self.HAS_MKVTOOLNIX))
        # logger.error('input_file = "{}"'.format(input_file))
        if self.HAS_MKVTOOLNIX and \
                os.path.exists(input_file):
            # input_file.endswith('.mkv'):
            self._mkv_file = input_file
            self._chapters_file = self._remove_starting_tmp_string(input_file[:-4] + '-chapters.txt')
            # remove tmp_ from begining of filename
            self._output_file = self._remove_starting_tmp_string(self._mkv_file)
            # logger.error('self._mkv_file\n{}'.format(self._mkv_file))
            # logger.error('self._chapters_file\n{}'.format(self._chapters_file))
            # logger.error('self._tag_file\n{}'.format(self._tag_file))
            # logger.error('self._output_file\n{}'.format(self._output_file))

            if not self._create_chapters():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('failed to extract chapters!')
                return False
            ''' write chapters file '''
            try:
                with open(self._chapters_file, 'w', encoding='utf-8') as f:
                    f.writelines(self._out)
            except:
                try:
                    os.remove(self._chapters_file)
                except:
                    pass
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('failed to write chapters file!')
                return False
            ''' write tags file '''
            tags = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE Tags SYSTEM "matroskatags.dtd">
<Tags>
    <Tag>
        <Simple>
            <Name>COMMENT</Name>
            <String>Created with {0}</String>
        </Simple>
    </Tag>
    <Tag>
        <Simple>
            <Name>ALBUM</Name>
            <String>PyRadio Playlist: {1}</String>
        </Simple>
    </Tag>
    <Tag>
        <Simple>
            <Name>TITLE</Name>
            <String>Station: {2}</String>
        </Simple>
    </Tag>
</Tags>
'''.format('PyRadio ' + self._cnf.current_pyradio_version, self._playlist, self._list[0][1].strip())
            try:
                with open(self._tag_file, 'w', encoding='utf-8') as f:
                    f.writelines(tags)
            except:
                try:
                    os.remove(self._tag_file)
                except:
                    pass
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('failed to write tag file!')
                return False
            return True
        else:
            logger.error('mkvmerge or input file not found')
            return False

    def _create_chapters(self):
        zero_time = self._list[0][0]
        for i, n in enumerate(self._list):
            current_time = n[0] - zero_time
            self._out.append('CHAPTER{0:0>2}={1}\n'.format(
                i+1, self.chapter_time_from_timedelta(current_time)
                )
            )
            self._out.append('CHAPTER{0:0>2}NAME={1}\n'.format(i+1, n[1]))
        return True

    @classmethod
    def chapter_time_from_datetime(cls, a_datetime):
        return '{0:0>2}:{1:0>2}:{2:0>2}.{3:0>3}'.format(
                a_datetime.hour,
                a_datetime.minute,
                a_datetime.second,
                int(a_datetime.microsecond/1000)
                )

    @classmethod
    def chapter_time_from_timedelta(cls, a_timedelta):
        h, rem = divmod(a_timedelta.seconds, 3600)
        m, s = divmod(rem, 60)
        n = int(a_timedelta.microseconds/1000)
        return '{0:0>2}:{1:0>2}:{2:0>2}.{3:0>3}'.format(
            h, m, s, n
        )


class PlayerCache():

    _dirty = False

    _data = {
            'mpv': [
                '--cache-secs=20',
                '--cache=yes',
                '--cache-on-disk=yes',
                '--demuxer-cache-wait=yes',
                '--demuxer-readahead-secs=20',
                ],
            'mplayer': [
                '-cache', '312',
                '-cache-min', '80'
                ],
            'vlc': [
                 '--network-caching',
                 '20000'
                 ]
            }

    _bitrate = '128'

    def __init__(self, player_name, data_dir, recording):
        self._player_name = player_name
        self._recording = recording
        data_file = os.path.join(data_dir, 'buffers')
        if os.path.exists(data_file):
            try:
                os.unlink(data_file)
            except (FileNotFoundError, PermissionError, OSError):
                pass

    @property
    def cache(self):
        if self._player_name == 'mpv':
            self._on_disk()
        if self._player_name != 'vlc':
            return self._data[self._player_name]
        out = self._data['vlc']
        out[1] = str(int(out[1]))
        return out

    @property
    def delay(self):
        if self._player_name == 'mpv':
            return int(self._data['mpv'][0].replace('--cache-secs=', ''))
        elif self._player_name == 'mplayer':
            return int(self._data['mplayer'][1])
        else:
            return int(int(self._data['vlc'][1]) / 1000)

    @delay.setter
    def delay(self, a_delay):
        try:
            x = int(a_delay)
        except ValueError:
            return

        if self._player_name == 'vlc':
            self._data['vlc'][1] = str(x * 1000)
        else:
            str_x = str(x)
            if self._player_name == 'mpv':
                self._data['mpv'][0] = '--cache-secs=' + str_x
                x -= 1
                self._data['mpv'][-1] = '--demuxer-readahead-secs=' + str(x)
            elif self._player_name == 'mplayer':
                self._data['mplayer'][1] = str_x
        self._dirty = True

    @property
    def station_delay(self):
        return self.delay

    @station_delay.setter
    def station_delay(self, value):
        if '@' in value:
            sp = value.split('@')
            self.delay, self._bitrate = sp
        else:
            self.delay = value
            self._bitrate = '128'

    def _on_disk(self):
        if self._recording() > 0:
            self._data['mpv'][2] = '--cache-on-disk=no'
            return
        try:
            virt = psutil.virtual_memory()
        except:
            self._data['mpv'][2] = '--cache-on-disk=no'
            return

        if virt.available > 500000:
            self._data['mpv'][2] = '--cache-on-disk=no'
        else:
            self._data['mpv'][2] = '--cache-on-disk=yes'


def probePlayer(config, requested_player=''):
    ''' Probes the multimedia players which are
        available on the host system. '''
    if logger.isEnabledFor(logging.INFO):
        logger.info('Probing available multimedia players...')
    implementedPlayers = Player.__subclasses__()
    if logger.isEnabledFor(logging.INFO):
        logger.info('Implemented players: ' +
                    ', '.join([player.PLAYER_NAME
                              for player in implementedPlayers]))
    for player in implementedPlayers:
        ret = check_player(player)
        if ret is not None:
            if ret not in available_players:
                available_players.append(ret)
    if logger.isEnabledFor(logging.INFO):
        logger.info('Available players: ' +
                    ', '.join([player.PLAYER_NAME
                              for player in available_players]))
    config.AVAILABLE_PLAYERS = available_players[:]
    if requested_player:
        req = requested_player.split(',')
        for r_player in req:
            if r_player == 'cvlc':
                r_player = 'vlc'
            for a_found_player in available_players:
                if a_found_player.PLAYER_NAME == r_player:
                    return a_found_player
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'Requested player "{requested_player}" not supported')
        return None
    else:
        return available_players[0] if available_players else None

def check_player(a_player):
    try:
        p = subprocess.Popen([a_player.PLAYER_CMD, '--help'],
                             stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE,
                             shell=False)
        p.terminate()

        if logger.isEnabledFor(logging.INFO):
            logger.info('%s supported.', str(a_player))
        return a_player
    except OSError:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%s not supported.', str(a_player))
        return None
