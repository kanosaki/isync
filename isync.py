# -*- coding: utf-8 -*-

# iSync: Walkman等のデバイスと、iTunesのプレイリストを同期します

# Configs
DEFAULT_CONFIG_FILENAME = 'iSyncConfig.json'

SYSTEM_PLAYLISTS = set([ 'Libaray', 'ライブラリ' ])

import plistlib
import sys
import os
import platform
import shutil
import urllib.request
import glob
import datetime
import re
import string
import logging
import math
import json
import concurrent.futures
import queue
import inspect
from logging import error, warn, info
from optparse import OptionParser

if sys.version < '3.3':
    raise 'Python 3.3 or above required.'

FILEDIR = os.path.abspath(os.path.dirname(__file__))

def cached_property(f):
    def get(self):
        try:
            return self._property_cache[f]
        except AttributeError:
            self._property_cache = {}
            x = self._property_cache[f] = f(self)
            return x
        except KeyError:
            x = self._property_cache[f] = f(self)
            return x
    return property(get)

# --------------------------------
#  Main class
# --------------------------------
class Main:
    def __init__(self):
        self._init_logger()
        self.args = CommandArguments()

    def start(self):
        self.sync()
        if self.env.is_win:
            input()
      
    def create_syncer(self):
        if self.config.is_dry:
            return DryLibrarySyncer
        else:
            return LibrarySyncer

    def sync(self):
        syncerClass = self.create_syncer()
        syncer = syncerClass(
                self.library,
                self.config,
                self.device)
        syncer.start()

    @property
    def env(self):
        return EnvironmentBuilder.create()
    
    @cached_property
    def config(self):
        info("Reading configurations...")
        try:
            path = self.args.config
            return Config.load(self.args, path)
        except Exception as e:
            warn(e)
            warn("Unable to read configuration, creating new one.")
            return Config.prepare_default(self.library)
    
    @cached_property
    def device(self):
        info("Searching device...")
        devices = list(DeviceLocator(self.env).find_all())
        if len(devices) < 1:
            abort("No suitable device found.")
        elif len(devices) > 1:
            warn("Multi suitable devices found. I will use {0} for syncing.".format(devices[0]))
        return devices[0]

    @cached_property
    def library(self):
        try:
            return Library(self.env.itunes_libfile())
        except Exception as e:
            error(e)
            abort("No iTunes library found.")

    def _init_logger(self):
        logging.basicConfig(level=logging.DEBUG)

class CommandArguments:
    def __init__(self):
        parser = OptionParser()
        parser.add_option('-c', '--config', action='store', type='string', dest='config')
        parser.add_option('-d', '--dry', action='store_true', dest='dry')
        self._opts, _ = parser.parse_args()

    def __getattr__(self, key):
        return getattr(self._opts, key)

class VoidObject:
    def __getattr__(self, key):
        return None
    

class Config:
    def __init__(self, dic, args, path=DEFAULT_CONFIG_FILENAME):
        self._dic = dic
        self._path = path
        self._args = args

    def __getattr__(self, key):
        return self._dic[key]

    def _inject_libaray(self, library):
            self._dic['library_path'] = library.path
            self._dic['target_playlists'] = dict(
                    (pl.name, False) 
                    for pl in library.playlists 
                    if not pl.is_system)

    @property
    def is_dry(self):
        return self._args.dry
    
    @staticmethod
    def prepare_default(library=None):
        dic = {
            'library_path' : "<Path to iTunes Libaray.xml>",
            'target_playlists' : { '<Playlist Name>' : False },
            'force_update' : False,
            'keep_removed_files' : False,
            }
        cfg = Config(dic, VoidObject())
        if library is not None:
            cfg._inject_libaray(library)
        cfg.save()
        return cfg

    def __str__(self):
        return 'Config({})'.format(str(self._dic))

    def save(self, path=None):
        path = path or self._path
        with open(path, 'w') as f:
            json.dump(self._dic, f, indent=4)

    @staticmethod
    def load(args=None, path=None):
        path = path or DEFAULT_CONFIG_FILENAME
        args = args or CommandArguments()
        with open(path) as f:
            dic = json.load(f)
            return Config(dic, args, path)


# --------------------------------
#  Utilities {{{
# --------------------------------

def id_fn(x):
    return x

def void_fn(*args, **kw):
    pass

def abort(*args):
    print(*args, file=sys.stderr)
    sys.exit(-1)

class ItemWrapperMixin:
    def __init__(self, wrapper, items=None):
        self.wrapper = wrapper
        if items is not None:
            super().__init__(items)

    def __getitem__(self, key):
        return self.wrapper(super().__getitem__(key))

    def __iter__(self):
        for item in super().__iter__():
            yield self.wrapper(item)

class WrapDict(ItemWrapperMixin, dict): pass
class WrapList(ItemWrapperMixin, list): pass


class NameAccessMixin:
    def __getattr__(self, name):
        if name.startswith('_'): # Ignore attribute starts with '_'
            return super().__getattr__(name)
        ename = self._name_conversion(name)
        return self[ename]

    def _name_conversion(self, name):
        return ' '.join(list(map(str.capitalize, name.split('_'))))

def fixfilename(name):
    return FilenameFixer.instance.filter(name)


ValidFilePathChars = set(iter(
    "-_.() " + string.ascii_letters + string.digits))
class FilenameFixer:
    def filter(self, expr):
        return ''.join(self._filter_invalid_dirname(expr))
        return os.path.join(self.root_dir, dirname)

    def _filter_invalid_dirname(self, name):
        return filter(lambda c : c in ValidFilePathChars, name)

FilenameFixer.instance = FilenameFixer()

class SwitchFn:
    def __init__(self, mainfn, altfn=void_fn):
        self.mainfn = mainfn
        self.is_altered = False
        self.altfn = altfn

    def switch(self):
        self.is_altered = not self.is_altered

    def use_altfn(self):
        self.is_altered = True

    def use_mainfn(self):
        self.is_altered = False

    def __set__(self, value):
        self.is_altered = value

    def __call__(self, *args, **kw):
        if self.is_altered:
            self.mainfn(*args, **kw)
        else:
            self.altfn(*args, **kw)

# }}}
# --------------------------------

# --------------------------------
#  Actions {{{
# --------------------------------
class Executor:
    def __init__(self):
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._history = queue.deque()

    def submit(self, f, *args, **kw):
        self._executor.submit(f, *args, **kw)

class DryExecutor(Executor):
    def submit(self, f, *args, **kw):
        self._executor.submit(f.dryrun, *args, **kw)

class ExecutorService(dict):
    DEFAULT_KEY = '_default'
    def __init__(self, klass=Executor):
        self.default_name = self.DEFAULT_KEY
        self[self.default_name] = klass()

    def _get_default(self):
        return self[self.default_name]

    def _set_default(self, val):
        self[self.default_name] = val

    default = property(_get_default, _set_default)


ExecutorService.root = ExecutorService()

class WorkerMixin:
    def __new__(cls, *args, **kw):
        newobj = super().__new__(cls)
        try:
            callerobj = inspect.stack()[1][0].f_locals['self']
            newobj._executor = callerobj._executor
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            newobj._executor = ExecutorService.root.default
        return newobj

    def submit(self, acton, *args, **kw):
        self._executor.submit(action, *args, **kw)

class Action:
    is_atomic = False
    is_dry = False
    def start(self, *args, dry=False, **kw):
        if self.is_dry or dry:
            self.dryrun(*args, **kw)
        else:
            self.run(*args, **kw)
    __call__ = start


class FileCopyAction(Action):
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def run(self):
        shutil.copy(self.src, self.dst)

    def dryrun(self, print_into=True):
        if print_into:
            info(str(self))

    def __str__(self):
        return "COPY {1} -> {2}".format(self.src, self.dst)



# }}}
# --------------------------------

# --------------------------------
#  Library handlers {{{
# --------------------------------

class Library:
    def __init__(self, pathorfile=None, env=None):
        self.file = pathorfile or find_library()
        self.lib = plistlib.readPlist(self.file)
        self._create_playlistmap()
        self._track_factory = self._create_track_factory(env)

    def _get_path(self):
        try:
            return self._path
        except AttributeError:
            self._path = self._try_get_path()
            return self._path
    
    def _try_get_path(self):
        if os.path.exists(self.file):
            return self.file
        else:
            raise Exception('This library created by stream')

    def _set_path(self, val):
        self._path = val

    path = property(fget=_get_path, fset=_set_path)

    def track(self, track_id):
        return self.tracks[str(track_id)]

    def playlist_by_name(self, playlist_name):
        return self._playlists_map[playlist_name]

    @cached_property
    def tracks(self):
        return WrapDict(self._build_track, self.lib['Tracks'])

    @cached_property
    def playlists(self):
        return WrapList(self._build_playlist, self.lib['Playlists'])

    def _create_playlistmap(self):
        pl_map = {}
        for playlist in self.playlists:
            pl_map[playlist.name] = playlist
        self._playlists_map = pl_map

    def _build_playlist(self, dic):
        return Playlist(self, dic)

    def _build_track(self, dic):
        return self._track_factory(dic)

    def _create_track_factory(self, env):
        if env is None:
            env = EnvironmentBuilder.create()
        def factory(track_dic):
            return EnvTrackAdapter(Track(track_dic), env)
        return factory


class Track(NameAccessMixin, dict):
    pass


class Playlist(NameAccessMixin, dict):
    def __init__(self, lib, dic):
        self.lib = lib
        dict.__init__(self, dic)
    
    @cached_property
    def tracks(self):
        return list(self._collect_tracks())

    def _collect_tracks(self):
        for track in self['Playlist Items']:
            try:
                track_id = track['Track ID']
                yield self.lib.track(track_id)
            except KeyError:
                warn("Warning: Track ID", track_id, "is not found in library")

    @property
    def persistent_id(self):
        return self['Playlist Persistent ID']

    # Smart Playlist
    @property
    def is_smart(self):
        return 'Smart Info' in self

    # System Playlist
    # For example: Musics, Videos, Podcasts, iTunes DJ, Genius, etc... 
    @property
    def is_system(self):
        return 'Distinguished Kind' in self or self.name in SYSTEM_PLAYLISTS
# }}}
# --------------------------------

# --------------------------------
#  Environment Definitions {{{
# --------------------------------
class EnvironmentBuilder:
    def environment(self):
        os_name = platform.system()
        if os_name == 'Windows':
            return Windows()
        elif os_name == 'Darwin':
            return MacOSX()
        else:
            raise RuntimeError(os_name + " is not supported.")

    @staticmethod
    def create():
        builder = EnvironmentBuilder()
        return builder.environment()


class Environment:
    is_win = False
    is_mac = False
    def homedir(self):
        return os.environ['HOME']

    def itunes_dir(self):
        return os.path.join(self.homedir(), 'Music', 'iTunes')

    def itunes_libfilename(self):
        return 'iTunes Music Library.xml'

    def itunes_libfile(self):
        return os.path.join(self.itunes_dir(), self.itunes_libfilename())

    def url_to_path(self, url):
        quoted_path = urllib.request.urlparse(url).path
        return urllib.request.unquote(quoted_path)


class MacOSX(Environment):
    is_mac = True
    def devicedirs(self):
        return glob.glob("/Volumes/*")


class Windows(Environment):
    is_win = True
    def homedir(self):
        return os.environ['HOMEPATH']

    def url_to_path(self, path):
        return super().url_to_path(path)[1:] # Remove first /(slash)

    def devicedirs(self):
        for charcode in range(ord('D'), ord('Z') + 1):
            yield chr(charcode) + ":"


class EnvTrackAdapter:
    def __init__(self, track, env):
        self.track = track
        self.env = env
    
    @cached_property
    def path(self):
        return self.env.url_to_path(self.location)

    @cached_property
    def _stat(self):
        return os.stat(self.path)

    @cached_property
    def filesize(self):
        return self._stat.st_size

    def write_to(self, dst_path):
        shutil.copy(self.path, dst_path)

    def __getattr__(self, key):
        return getattr(self.track, key)
# }}}
# --------------------------------

# --------------------------------
#  Device Definitions {{{
# --------------------------------
class Device:
    pass


class Walkman(Device):
    def __init__(self, device_dir):
        self.root_dir = device_dir

    @staticmethod
    def is_suitable(dev_dir):
        capability_file_pat = os.path.join(dev_dir, "capability_*.xml")
        return len(glob.glob(capability_file_pat)) > 0
    
    def playlist_dirpath(self, playlist):
        dirname = fixfilename(playlist.name)
        return os.path.join(self.root_dir, dirname)

    def __str__(self):
        return "Walkman at {0}".format(self.root_dir)

# }}}
# --------------------------------

# --------------------------------
#  Sync executors {{{
# --------------------------------
class DeviceLocator:
    def __init__(self, env):
        self.env = env

    def devices(self): # -> list<Device>
        return [ Walkman ]

    def suitables(self, dev_dir): # -> iter<Device>
        return (dev(dev_dir) for dev in self.devices() if dev.is_suitable(dev_dir))

    def find_all(self): # -> iter<Devices>
        for dev_dir in self.env.devicedirs():
            yield from self.suitables(dev_dir)


class ActualFile(WorkerMixin):
    def __init__(self, path):
        """path: indexed file path"""
        self.path = path

    @cached_property
    def _stat(self):
        return os.stat(self.path)
        
    @property
    def last_modified(self):
        return datetime.datetime.fromtimestamp(self._stat.st_mtime)

    def copy_track(self, track):
        shutil.copy(track.path, self.path)

    def update_track(self, track):
        if not os.path.exists(self.path) or\
                track.date_modified > self.last_modified:
            self.copy_track(track)

class DryActualFile(ActualFile):
    def copy_track(self, track):
        info("DRY: copy {} {}".format(track.path, self.path))


class SyncDirectory(WorkerMixin):
    RE_PAT = re.compile(r'\d+\s(.+)')
    def __init__(self, path, expected_files_count, force_write=False, dryrun=False):
        self.path = path
        self.files_map = self.collect_files()
        self.force_write = force_write
        self.index_digits = int(math.log10(expected_files_count)) + 1

    def collect_files(self): # -> dict<str, str>
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        fs = {}
        for fname in os.listdir(self.path):
            match = self.RE_PAT.match(fname)
            if match:
                fs[match.group(1)] = fname
        return fs

    def update_track_at(self, track, pos):
        if track.name in self.files_map:
            self.update_filename(track, pos)
        else:
            self.copy_new(track, pos)

    def actual_name(self, track, pos):
        index = str(pos).zfill(self.index_digits)
        escaped_name = fixfilename(track.name)
        _, extension = os.path.splitext(track.path)
        return '{0} {1}{2}'.format(index, escaped_name, extension)

    def actual_path(self, track, pos):
        name = self.actual_name(track, pos)
        return os.path.join(self.path, name)

    def update_filename(self, track, pos):
        newname = self.actual_name(track.name, pos)
        oldname = self.files_map[track.name]
        if newname != oldname:
            self.move_file(oldname, newname)

    def move_file(self, oldname, newname):
        oldpath = os.path.join(self.path, oldname)
        newpath = os.path.join(self.path, newname)
        self.exec_move(oldpath, newpath)

    def exec_move(self, src, dst):
        shutil.move(src, dst)

    def copy_new(self, track, pos):
        path = self.actual_path(track, pos)
        actual_file = ActualFile(path)
        actual_file.update_track(track)

    def create_actual_file(self, path):
        return ActualFile(path)


class DrySyncDirectory(SyncDirectory):
    def exec_move(self, oldname, newname):
        info("DRY: move {} {}".format(oldpath, newpath))

    def create_actual_file(self, path):
        return DryActualFile(path)


class LibrarySyncer(WorkerMixin):
    def __init__(self, library, config, device):
        self.library = library
        self.config = config
        self.device = device

    def sync(self):
        for playlist in self.prepare_playlists():
            dst_dir = self.targetdir(playlist)
            syncer = PlaylistSyncer(playlist, dst_dir)
            syncer.sync()

    def targetdir(self, playlist): # -> SyncDirectory
        dirpath = self.device.playlist_dirpath(playlist)
        return SyncDirectory(dirpath, len(playlist.tracks))
    
    def prepare_playlists(self): # -> iter<Playlist>
        for pname in self.config.target_playlists:
            try:
                yield self.library.playlist_by_name(pname)
            except KeyError:
                warn("Playlist {} was not found in library".format(pname))

class DryLibrarySyncer(LibrarySyncer):
    def targetdir(self, playlist):
        dirpath = self.device.playlist_dirpath(playlist)
        return DrySyncDirectory(dirpath, len(playlist.tracks))


class PlaylistSyncer(WorkerMixin):
    def __init__(self, playlist, dst_dir):
        """playlist: Playlist, dst_dir: SyncDirectory"""
        self.playlist = playlist
        self.targetdir = dst_dir

    def sync(self):
        tracks = self.playlist.tracks
        tracks_count = len(tracks)
        for track, index in zip(tracks, range(tracks_count)):
            self.targetdir.update_track_at(track, index)


# }}}
# --------------------------------

if __name__ == '__main__':
    m = Main()
    m.start()

