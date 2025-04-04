# -*- coding: utf-8 -*-
import logging
import locale
import io
import csv
import curses
from os import rename, remove, access, X_OK
from os.path import exists, dirname, join
from shutil import which
from rich import print
from enum import IntEnum

logger = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, "")

""" Theming constants """
def FOREGROUND():
    return 0
def BACKGROUND():
    return 1

# for pop up window
CAPTION = 2
BORDER = 3

class Station(IntEnum):
    name = 0
    url = 1
    encoding =2
    icon = 3
    profile = 4
    buffering = 5
    http = 6
    volume = 7
    referer = 8

M_STRINGS = {
	'checking-playlist': ' (Checking Playlist)',
	'session-locked': ' (Session Locked)',
	'session-locked-title': 'Session Locked',
	'win-title': 'Your Internet Radio Player',
	'init_': 'Initialization: ',
	'connecting_': 'Connecting to: ',
	'playing_': 'Playing: ',
	'buffering_': 'Buffering: ',
	'station_': 'Station: ',
	'station_buffering': 'Station Buffering',
	'station-open': ' - Opening connection...',
	'selected_player_': 'Selected player: ',
	'down-icon': 'Downloading icon...',
	'player-acivated_': ': Player activated!!!',
	'hist-empty': 'History is empty!!!',
	'hist-first': 'Already at first item!!!',
	'hist-last': 'Already at last item!!!',
    'muted': '[Muted] ',
    'title_': 'Title: ',
    'player-stopped': 'Player is stopped!',
    'plb-stopped': 'Playback stopped',
    'html-player-stopped': '<div class="alert alert-danger">Player is <b>stopped!</b></div>',
	'press-?': ' Press ? for help',
	'error-str': 'error',
	'vol_': 'Vol: ',
    'error-403': 'Server returned "Forbidden" (error 403)',
    'error-404': 'Station does not exist (error 404)',
    'error-503': 'Service not available (error 503)',
    'error-1000': 'Player terminated abnormally! (error 1000)',
    'error-1001': 'Connection failed (error 1001)',
    'error-1002': 'No stream found (error 1002)',
    'error-1003': 'Connection refused (error 1003)',
    'error-1004': 'Unrecognized file format (error 1004)',
    'error-1005': 'DNS Resolution failure (error 1005)',
    'error-1006': 'Server is unreachable (error 1006)',
    'error-1007': 'Permission denied (error 1007)',
    'error-1008': 'Unrecognized file format (error 1008)',
}

""" Messages to display when player starts / stops
    Used in log to stop runaway threads from printing
    messages after playback is stopped """
player_start_stop_token = {
    0:       M_STRINGS['init_'],
    1:       M_STRINGS['plb-stopped'],
    3:       M_STRINGS['player-acivated_'],
    403:     M_STRINGS['error-403'],
    404:     M_STRINGS['error-404'],
    503:     M_STRINGS['error-503'],
    1000:    M_STRINGS['error-1000'],
    1001:    M_STRINGS['error-1001'],
    1002:    M_STRINGS['error-1002'],
    1003:    M_STRINGS['error-1003'],
    1004:    M_STRINGS['error-1004'],
    1005:    M_STRINGS['error-1005'],
    1006:    M_STRINGS['error-1006'],
    1007:    M_STRINGS['error-1007'],
    1008:    M_STRINGS['error-1008'],
}

seconds_to_KB_128 = (
    0, 78, 93, 109, 125, 140, 156, 171, 187, 203, 218, 234,
    250, 265, 281, 296, 312, 328, 343, 359, 375, 390, 406,
    421, 437, 453, 468, 484, 500, 515, 531, 546, 562, 578,
    593, 609, 625, 640, 656, 671, 687, 703, 718, 734, 750,
    765, 781, 796, 812, 828, 843, 859, 875, 890, 906, 921, 937
)

seconds_to_KB_192 = (
    0, 117, 140, 164, 187, 210, 234, 257, 281, 304, 328, 351,
    375, 398, 421, 445, 468, 492, 515, 539, 562, 585, 609, 632,
    656, 679, 703, 726, 750, 773, 796, 820, 843, 867, 890, 914,
    937, 960, 984, 1007, 1031, 1054, 1078, 1101, 1125, 1148, 1171,
    1195, 1218, 1242, 1265, 1289, 1312, 1335, 1359, 1382, 1406
)

seconds_to_KB_320 = (
    0, 195, 234, 273, 312, 351, 390, 429, 468, 507, 546, 585, 625,
    664, 703, 742, 781, 820, 859, 898, 937, 976, 1015, 1054, 1093,
    1132, 1171, 1210, 1250, 1289, 1328, 1367, 1406, 1445, 1484, 1523,
    1562, 1601, 1640, 1679, 1718, 1757, 1796, 1835, 1875, 1914, 1953,
    1992, 2031, 2070, 2109, 2148, 2187, 2226, 2265, 2304, 2343
)


class STATES():
    ANY = -1
    RESET = 0
    INIT = 1
    CONNECT = 2
    PLAY = 10
    TITLE = 11
    STOPPED = 12
    # Do not move it!
    PLAYER_ACTIVATED = 13

    CONNECT_ERROR = 100
    VOLUME = 101
    BUFF_MSG = 102
    BUFFER = 103

    ERROR_NO_PLAYER = 200
    ERROR_DEPENDENCY = 201
    ERROR_CONNECT = 202
    ERROR_START = 203

"""
Format of theme configuration
    Name, color_pair, foreground, background
If foreground == 0, color can be edited
If > 0, get color from list item referred to by number
Same for the background
"""
_param_to_color_id = {
    'Extra Func': (12, ),
    'PyRadio URL': (11, ),
    'Messages Border': (10, ),
    'Status Bar': (8, 9),
    'Stations': (1, 2),
    'Active Station': (3, ),
    'Active Cursor': (6, 7),
    'Normal Cursor': (4, 5),
}

THEME_ITEMS = (
    ('PyRadio URL', 2, 0, 3),
    ('Messages Border', 3, 0, 3),
    ('Status Bar', 7, 0, 0),
    ('Stations', 5, 0, 0),
    ('Active Station', 4, 0, 3),
    ('Normal Cursor', 6, 0, 0),
    ('Active Cursor', 9, 0, 0),
    ('Edit Cursor', 8, 0, 0)
)

def describe_playlist(value):
    # Check if the value is within the range of the enum
    if value < 0 or value >= len(Station.__members__):
        # Return the default message if the value is out of range
        return f"Playlist has {Station.name.name} {Station.url.name}"

    # Collect all names from 0 to the given value
    names = [station.name for station in list(Station)[:value + 1]]

    # Join the names with spaces and return the result
    return f"Playlist has {' '.join(names)}"


def erase_curses_win(Y, X, beginY, beginX, char=' ', color=5):
    ''' empty a part of the screen
    '''
    empty_win = curses.newwin(
        Y - 2, X - 2,
        beginY + 1, beginX + 1
    )
    empty_win.bkgdset(char, curses.color_pair(color))
    empty_win.erase()
    empty_win.refresh()

def is_rasberrypi():
    ''' Try to detest rasberry pi '''
    try:
        with io.open('/sys/firmware/devicetree/base/model', 'r', encoding='utf-8') as m:
            if 'raspberry pi' in m.read().lower():
                return True
    except Exception:
        pass
    return False

    # if exists('/usr/bin/raspi-config'):
    #     return True
    # return False

def hex_to_rgb(hexadecimal):
    n = hexadecimal.lstrip('#')
    return tuple(int(n[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

def curses_rgb_to_hex(rgb):
    return rgb_to_hex(tuple(int(y * 255 / 1000) for y in rgb))

def rgb_to_curses_rgb(rgb):
    return tuple(int(y *1000 / 255) for y in rgb)


class StationsChanges():
    '''
    #########################################################################
    #                                                                       #
    #                         stations.csv change                           #
    #                                                                       #
    #########################################################################
    #                                                                       #
    # This section will include the changes of stations.csv                 #
    #                                                                       #
    # version_changed                                                       #
    #   The version the changes appeared (calculated)                       #
    #                                                                       #
    # It will also contain three lists:                                     #
    #   added     - list of stations added                                  #
    #   changed   - list of stations changed                                #
    #   deleted   - list of stations deleted                                #
    #                                                                       #
    # The "changed" list will be of format:                                 #
    #           [[ x , [station name, station url ]]                        #
    # where:                                                                #
    #           x : 0 / 1 index changed (0: name, 1: URL)                   #
    #                                                                       #
    #########################################################################
    '''
    version_changed = None

    '''
    versions = {
        (0, 9, 2):                       # 0.9.2 version
        [
            [...........],                 # added
            [x, [...........]],            # changed
            [...........],                 # deleted
        ],
        (0, 9, 1):                       # 0.9.1 version
        [
            [...........],                 # added
            [x, [...........]],            # changed
            [...........],                 # deleted
        ]
    ]
    '''
    versions = {
        (0, 9, 2):
        [
            [
                ['Groove Salad Classic (Early 2000s Ambient)', 'https://somafm.com/gsclassic.pls'],
                ['n5MD Radio (Ambient and Experimental)', 'https://somafm.com/n5md.pls'],
                ['Vaporwaves [SomaFM]', 'https://somafm.com/vaporwaves.pls'],
                ['The Trip: [SomaFM]', 'https://somafm.com/thetrip.pls'],
                ['Heavyweight Reggae', 'https://somafm.com/reggae.pls'],
                ['Metal Detector', 'https://somafm.com/metal.pls'],
                ['Synphaera Radio (Space Music)', 'https://somafm.com/synphaera.pls']
            ], # added

            [
                [0, ['Reggae Dancehall (Ragga Kings)', 'https://raggakings.radio:8443/stream.ogg']]
            ], # changed

            [] # deleted
        ],

        (0, 9, 3):
        [
            [
                ['Radio Levač (Serbian Folk & Country)', 'http://213.239.205.210:8046/stream'],
                ['Radio 35 (Serbian and English Pop, Folk, Country & Hits)', 'http://stream.radio035.net:8010/listen.pls']
            ], # added
            [], # changed
            [], # deleted
        ],

        (0, 9, 3, 11, 5):
        [
            [], # added
            [
				['DanceUK', 'http://uk2.internet-radio.com:8024/listen.pls'],
				['JazzGroove', r'http://199.180.72.2:8015/listen.pls\?sid\=1'],
				['Metal Detector' 'http://somafm.com/metal.pls'],
            ], # changed
            [
				['Beyond Metal (Progressive - Symphonic)', 'http://streamingV2.shoutcast.com/BeyondMetal'],
				['Vox Noctem: Rock-Goth', 'http://r2d2.voxnoctem.de:8000/voxnoctem.mp3'],
            ], # deleted
        ],
    }

    keys = None
    _stations = None
    _stations_file = None
    _playlist_version = 0

    def __init__(self, config):
        self._cnf = config
        self._last_sync_file = join(self._cnf.state_dir, 'last-sync')
        self._asked_sync_file = join(self._cnf.state_dir, 'asked-sync')

        self.PLAYLIST_HAS_NAME_URL = 0
        self.PLAYLIST_HAS_NAME_URL_ENCODING = 1
        self.PLAYLIST_HAS_NAME_URL_ENCODING_ICON = 2
        self.counts = [0, 0, 0]

    def _read_version(self):
        the_file = join(dirname(__file__), '__init__.py')
        lin = ''
        with open(the_file, 'r', encoding='utf-8') as cfg:
            while not lin.startswith('version_info'):
                lin = cfg.readline().strip()
        lin = lin[15:].replace('(', '').replace(')', '')
        # this_version = tuple(map(int, lin.split(', ')))
        return eval(lin)

    def _read_synced_version(self, asked=False):
        in_file = self._asked_sync_file if asked else self._last_sync_file
        # print('in_file = "{}"'.format(in_file))
        if exists(in_file):
            try:
                with open(in_file, 'r', encoding='utf-8') as sync_file:
                    line = sync_file.readline().strip()
                    return eval(line)
            except:
                pass
        return None

    def write_synced_version(self, asked=False):
        out_file = self._asked_sync_file if asked else self._last_sync_file
        try:
            with open(out_file, 'w', encoding='utf-8') as sync_file:
                sync_file.write(self.version_to_write)
        except:
            return -5 if asked else -6
        return -3 if asked else 0

    def _open_stations_file(self):
        self._stations = []
        self._stations_file = join(self._cnf.stations_dir, 'stations.csv')
        self._playlist_version = self.PLAYLIST_HAS_NAME_URL
        if exists(self._stations_file):
            with open(self._stations_file, 'r', encoding='utf-8') as cfgfile:
                try:
                    for row in csv.reader(filter(lambda row: row[0]!='#', cfgfile), skipinitialspace=True):
                        if not row:
                            continue
                        try:
                            name, url = [s.strip() for s in row]
                            self._stations.append([name, url, '', ''])
                        except:
                            try:
                                name, url, enc = [s.strip() for s in row]
                                self._stations.append([name, url, enc, ''])
                                self._playlist_version = self.PLAYLIST_HAS_NAME_URL_ENCODING
                            except:
                                name, url, enc, onl = [s.strip() for s in row]
                                self._stations.append([name, url, enc, onl])
                                self._playlist_version = self.PLAYLIST_HAS_NAME_URL_ENCODING_ICON
                except:
                    self._stations = []
                    self._playlist_version = self.PLAYLIST_HAS_NAME_URL
                    return False
            return True
        return False

    def _save_stations_file(self, print_messages=True):
        self._out_stations_file = join(self._cnf.stations_dir, 'stations-new.csv')
        self._bck_stations_file = join(self._cnf.stations_dir, 'stations.csv.bck')
        try:
            with open(self._out_stations_file, 'w', encoding='utf-8') as cfgfile:
                writter = csv.writer(cfgfile)
                for a_station in self._stations:
                    if a_station[3] != '':
                        a_station[3] = a_station[3]['image']
                    writter.writerow(self._format_playlist_row_out(a_station))
        except:
            print('Error: Cannot create the updated stations file.')
            print('       The updated stations file would be\n         "{}".'.format(self._out_stations_file))
            return False
        ''' rename stations.csv to stations.csv.bck '''
        try:
            rename(self._stations_file, self._bck_stations_file)
        except:
            print('Error: Cannot create the stations backup file.')
            print('       The updated stations file can be found at\n         "{}".'.format(self._out_stations_file))
            return False
        ''' rename stations-new.csv to stations.csv '''
        try:
            rename(self._out_stations_file, self._stations_file)
        except:
            print('Error: Cannot rename the updated stations file.')
            print('       The updated stations file can be found at\n         "{}".'.format(self._out_stations_file))
            print('       The old stations file has been backed up as\n         "{}".'.format(self._bck_stations_file))
            return False
        ''' remove bck file '''
        try:
            remove(self._bck_stations_file)
        except:
            pass
        if print_messages:
            print('File "stations.csv" updated...')
        return True

    def _format_playlist_row_out(self, a_row):
        ''' Return a 2-column if in old format,
            a 3-column row if has encoding, or
            a 4 column row if has online browser flag too '''
        if self._playlist_version == self.PLAYLIST_HAS_NAME_URL_ENCODING_ICON:
            return a_row
        elif self._playlist_version == self.PLAYLIST_HAS_NAME_URL_ENCODING:
            return a_row[:-1]
        else:
            return a_row[:-2]

    def _format_vesion(self, a_version_tuple):
        ret = str(a_version_tuple)
        ret = ret.replace('(', '')
        ret = ret.replace(')', '')
        ret = ret.replace(', ', '.')
        return ret

    def check_if_version_needs_sync(self, stop=None):
        ''' check if we need to sync stations.csv
            takes under consideration the answer
            the user gave at the TUI
        '''
        ret = self.stations_csv_needs_sync(print_messages=False)
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        self.asked_sync = self._read_synced_version(asked=True)
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        if self.version_changed == self.asked_sync:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('asked_sync is equal to version_changed!!!')
            return False
        return ret

    def stations_csv_needs_sync(self, print_messages=True, stop=None):
        ''' check if we need to sync stations.csv
            it will return true no matter what the user has
            replied about syncing, at the TUI

            Used by update_stations_csv()
        '''
        self.keys = [x for x in self.versions]
        self.keys.sort()
        # print('keys = {}'.format(self.keys))
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        self.last_sync = self._read_synced_version()
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        if exists(self._last_sync_file):
            try:
                with open(self._last_sync_file, 'r', encoding='utf-8') as sync_file:
                    line = sync_file.readline().strip()
                    self.last_sync = eval(line)
            except:
                ret = False
            if self.last_sync is None:
                ret = True
            else:
                ret = True if self.keys[-1] > self.last_sync else False
        else:
            if stop is not None:
                if stop():
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug('asked to stop! Terminating!')
                    return False
            ret = True

        if ret and self.last_sync is not None:
            self.keys.reverse()
            while self.keys[-1] <= self.last_sync:
                self.keys.pop()
            self.keys.reverse()
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        # print('keys = {}'.format(self.keys))
        self.version_changed = self.keys[-1]
        self.version_to_write = str(self.version_changed).replace('(', '').replace(')', '')
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        if print_messages:
            print('Updating "stations.csv"')
            print('Last updated version: {}'.format(self._format_vesion(self.version_changed)))
            print(' Last synced version: {}'.format(self._format_vesion(self.last_sync)))
        if stop is not None:
            if stop():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('asked to stop! Terminating!')
                return False
        if print_messages and not ret:
            print('Already synced: "stations.csv"')
        return ret

    def _format_playlist_row_in(self, a_row):
        ''' Return a 2-column if in old format,
            a 3-column row if has encoding, or
            a 4 column row if has online browser flag too '''
        while len(a_row) < 4:
            a_row.append('')
        return a_row

    def update_stations_csv(self, print_messages=True):
        ''' update stations.csv
            Returns:
                 1 : Update not needed
                 0 : All ok
                -1 : Cannot read stations.csv
                -2 : File not saved


        '''
        # if self.stations_csv_needs_sync(print_messages=print_messages):
        if self.stations_csv_needs_sync(print_messages=False):
            if not self._open_stations_file():
                if print_messages:
                    print('Cannot read "stations.csv"')
                return -1
            # for n in self._stations:
            #     print(n)

            for k in self.keys:
                if print_messages:
                    print('  From version: {}'.format('.'.join(map(str, k))))
                for n in self.versions[k][2]:
                    found = [x for x in self._stations if x[0] == n[0]]
                    if found:
                        for an_item in found:
                            if print_messages:
                                print('[red]    --- deleting: "[green]{}[/green]"[/red]'.format(an_item[0]))
                            self.counts[2] += 1
                            self._stations.pop(self._stations.index(an_item))
                for n in self.versions[k][1]:
                    found = []
                    if n[0] == 0:
                        found = [x for x in self._stations if x[0] == n[1][0] and x[1] != n[1][1]]
                    elif n[0] == 1:
                        found = [x for x in self._stations if x[1] == n[1][1] and x[0] != n[1][0]]
                    if found:
                        if print_messages:
                            print('[plum4]    +/- updating: "[green]{}[/green]"[/plum4]'.format(found[0][0]))
                        self.counts[1] += 1
                        index = self._stations.index(found[0])
                        self._stations[index] = self._format_playlist_row_in(n[1])
                for n in self.versions[k][0]:
                    found = [x for x in self._stations if x[0] == n[0]]
                    if not found:
                        if print_messages:
                            print('[magenta]    +++   adding: "[green]{}[/green]"[/magenta]'.format(n[0]))
                        self.counts[0] += 1
                        self._stations.append(self._format_playlist_row_in(n))

            if self._save_stations_file(print_messages=print_messages):
                ret = self.write_synced_version()
                if ret == -6:
                    if print_messages:
                        txt = '''
[red]Error:[/red] [magenta]PyRadio[/magenta] could not write the "last_sync" file.
This means that although stations have been synced, [magenta]PyRadio[/magenta] will try
to sync them again next time, which means that you may end up with
duplicate stations.

Please close all open programs and documents and create the file
[green]{0}[/green]
and write in it
      "[green]{1}[/green]" (no quotes).
                        '''.format(
                            self._last_sync_file,
                            self.version_to_write
                        )
                        print(txt)

                elif print_messages:
                    print('\n[bold]Summary[/bold]\n[magenta]    +++ added   :[/magenta]  {0}\n[plum4]    +/- updated :[/plum4]  {1}\n[red]    --- deleted :[/red]  {2}'.format(self.counts[0], self.counts[1], self.counts[2]))
                return ret
            return -2
        return 1

        # print('\n\n\n')
        # for n in self._stations:
        #     print(n)

def validate_resource_opener_path(a_file):
    # Check if the file exists
    if not exists(a_file):
        # If the file doesn't exist, try to find it using shutil.which
        full_path = which(a_file)
        if full_path is None:
            return None
        else:
            a_file = full_path
    # Check if the file is executable
    if not access(a_file, X_OK):
        return None
    # Return the validated path
    return a_file
