#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iSync: Walkman等のデバイスと、iTunesのプレイリストを同期します

# --------------------------------
# Languages {{{
# --------------------------------

import locale
# Set POSIX locale variables.
locale_key, encoding_name = locale.getlocale()
language_strings = {
    'ja_JP' : {
        "Python 3.3 or above required.": "Python 3.3以上をインストールして下さい。",
        "Reading configurations...": "設定を読み込んでいます・・・・",
        "Unable to read configuration, creating new one.": "設定ファイルを読み込めませんでした。新規に作成し続行します。",
        "Searching device...": "デバイスを探しています・・・",
        "No suitable device found.": "対応しているデバイスが見つかりませんでした",
        "Multi suitable devices found. I will use {0} for syncing.": "複数の使用可能デバイスが見つかりました、{0}を使用します",
        "No iTunes library found.": "iTuensライブラリが見つかりませんでした",
        "<Path to iTunes Libaray.xml>": "<iTunes ライブラリへのパス>",
        "<Playlist Name>": "<プレイリスト名>",
        "This library created by stream": "ストリームから作成されたライブラリでは実行できません。",
        "Warning: Track ID {0} is not found in library": "警告: トラックID{0}はデータベースから見つかりませんでした。データベースが破損しています",
        " is not supported.": "はサポートされていません",
        "Location of Track {} is not recorded on Library file.": "トラック{}の場所がライブラリに記録されていませんでした",
        "Playlist {} was not found in library": "設定ファイルに誤りがあります。プレイリスト「{}」はライブラリ中に存在しません。",
        "LibrarySyncer at {}": "LibrarySyncer at {}",
        "Following playlists will be synced": "以下のプレイリストが同期されます",
        "<No artist>": "<アーティスト無し>",
        "<No Title>": "<タイトル無し>",
        "Syncing {}/{}": "同期中 {}/{}",
        "Locaiton of Track {} is not recorded on Library file.": "{}のパスがライブラリ中に記録されていませんでした"
    }
}
if locale_key in language_strings:
    current_locale = language_strings[locale_key]
    def _i(key):
        """gettext's '_' like function"""
        try:
            return current_locale[key]
        except KeyError:
            return key
else:
    current_locale = "C"
    def _i(key):
        return key
# }}}
# --------------------------------

# --------------------------------
# Core configurations
# --------------------------------
APP_DESCRIPTION = _i('A simple synchronizer between iTunes and Walkman')
DEFAULT_CONFIG_FILENAME = 'iSyncConfig.json'
SYSTEM_PLAYLISTS = set([ 'Libaray', 'ライブラリ' ])
DEBUG_MODE = True
MUSICFILE_EXTENSIONS = ['mp3', 'm4a']

# Import list
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
import argparse
from logging import error, warn, info, debug

# Version check
if sys.version < '3.3':
    raise _i('Python 3.3 or above required.')

FILEDIR = os.path.abspath(os.path.dirname(__file__))

# Utility functions
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
        self.args = CommandArguments()
        self._init_logger()

    def start(self):
        self.sync()
        if self.env.is_win:
            input() # pause console for cmd.exe

    def create_syncer(self):
        if self.config.is_dry:
            info("Dry-run mode.")
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
        info(_i("Reading configurations..."))
        try:
            path = self.args.config
            return Config.load(self.args, path)
        except Exception as e:
            warn(e)
            warn(_i("Unable to read configuration, creating new one."))
            return Config.prepare_default(self.library)

    @cached_property
    def device(self):
        info(_i("Searching device..."))
        devices = list(DeviceLocator(self.env).find_all())
        if len(devices) < 1:
            abort(_i("No suitable device found."))
        elif len(devices) > 1:
            warn(_i("Multi suitable devices found. I will use {0} for syncing.").format(devices[0]))
        return devices[0]

    @cached_property
    def library(self):
        try:
            return Library(self.env.itunes_libfile())
        except Exception as e:
            error(e)
            abort(_i("No iTunes library found."))

    # DO NOT refer any attributes except 'args' to make sense of
    # logging.basicConfig
    def _init_logger(self):
        lvl = logging.INFO
        fmt='%(levelname)-5s %(message)s'
        if ('verbose' in self.args) or DEBUG_MODE:
            lvl = logging.DEBUG
            fmt='%(asctime)-15s %(levelname)-5s %(message)s'
        if 'logging' in self.args:
            lvl = getattr(logging, self.args.logging.upper())
        logging.basicConfig(level=lvl, format=fmt)

# DO NOT use logging functions
class CommandArguments:
    def __init__(self, args=None):
        parser = argparse.ArgumentParser(description=APP_DESCRIPTION)
        parser.add_argument('-c', '--config', metavar='PATH',
                            nargs='?', type=argparse.FileType('r'),
                            help=_i('Path to config file'))
        parser.add_argument('-d', '--dry', action='store_true',
                            help=_i('Dry-run mode.'))
        parser.add_argument('-v', '--verbose', action='store_true',
                            help=_i('Verbose output. Set logging level to DEBUG'))
        parser.add_argument('--logging',
                            nargs='?', choices=['ERROR', 'WARN', 'INFO', 'DEBUG'],
                            help=_i('Set logging level, default is WARN, overwrites "-v" option'))
        self._opts = parser.parse_args(args)

    def __contains__(self, key):
        return hasattr(self._opts, key) and (self[key] is not None)

    def __getattr__(self, key):
        return getattr(self._opts, key)

    def __getitem__(self, key):
        return getattr(self._opts, key)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        else:
            return default

class VoidObject:
    def __getattr__(self, key):
        return None

class Config:
    def __init__(self, dic, args, path=DEFAULT_CONFIG_FILENAME):
        dic.setdefault(None)
        self._dic = dic
        self._path = path
        self._args = args

    def __getattr__(self, key):
        return self._args.get(key) or self._dic[key]

    def get(self, key, default=None):
        return self._args.get(key) or self._dic.get(key) or default

    def __contains__(self, key):
        return (key in self._dic) or (key in self._args)

    def _inject_libaray(self, library):
            self._dic['library_path'] = library.path
            self._dic['target_playlists'] = dict(
                    (pl.name, False)
                    for pl in library.playlists
                    if not pl.is_system)

    def _dic_tryget(self, key):
        try:
            return self._dic[key]
        except KeyError:
            return None

    def inject(self, **kw):
        self._dic.update(kw)

    @property
    def is_dry(self):
        return self._args.dry or self._dic_tryget('dry')

    @staticmethod
    def prepare_default(library=None):
        dic = {
            'library_path' : _i("<Path to iTunes Libaray.xml>"),
            'target_playlists' : { _i('<Playlist Name>') : False },
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

def zipwithindex(iterable, start=0):
    index = start
    for item in iterable:
        yield (index, item)
        index += 1

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

class WrapDict(ItemWrapperMixin, dict):
    pass

class WrapList(ItemWrapperMixin, list):
    pass


class NameAccessMixin:
    def __getattr__(self, name):
        if name.startswith('_'): # Ignore attribute starts with '_'
            return getattr(super(), name)
        ename = self._convert_name(name)
        return self[ename]

    def get(self, key, default=None):
        ename = self._convert_name(key)
        if ename in self:
            return self[ename]
        else:
            return default

    def _convert_name(self, name):
        return ' '.join(list(map(str.capitalize, name.split('_'))))

def fixfilename(name):
    return FilenameFixer.instance.filter(name)


InvalidFilePathChars = set(list(iter('"<>|:*?\\/')) + list(map(chr, range(0, 31))))
class FilenameFixer:
    def filter(self, expr):
        return ''.join(self._filter_invalid_dirname(expr))

    def _filter_invalid_dirname(self, name):
        return filter(lambda c : c not in InvalidFilePathChars, name)

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

class IncompleteLibraryError(Exception):
    pass

# }}}
# --------------------------------

# --------------------------------
#  Actions {{{
# --------------------------------
class Executor:
    def __init__(self):
        self._history = queue.deque()
        self.init_worker()

    def init_worker(self):
        self.worker = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def submit(self, f, *args, **kw):
        # TODO: Add exception handling
        self.worker.submit(f, *args, **kw)

    def shutdown(self):
        self.worker.shutdown()
        self.init_worker()

class DryExecutor(Executor):
    def submit(self, f, *args, **kw):
        try:
            return super().submit(f.dryrun, *args, **kw)
        except AttributeError:
            info("DRYRUN: Running {}".format(repr(f)))


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
            callerobj = inspect.currentframe().f_back.f_locals['self']
            newobj._executor = callerobj._executor
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            debug("Creating new ExecutorRoot for {}".format(cls))
            newobj._executor = ExecutorService.root.default
        return newobj

    def submit(self, action, *args, **kw):
        return self._executor.submit(action, *args, **kw)

    def shutdown(self):
        self._executor.shutdown()

    def _inject_executor(self, executor):
        self._executor = executor

class Action:
    is_atomic = False
    is_dry = False
    def start(self, *args, dry=False, **kw):
        if self.is_dry or dry:
            self.dryrun(*args, **kw)
        else:
            self.run(*args, **kw)

    __call__ = start

    def dryrun(self, print_into=True):
        if print_into:
            debug(str(self))

    def on_complete(self):
        pass

class Task(list, Action):
    def run(self):
        for action in self:
            action.run()

    def dryrun(self):
        for action in self:
            action.dryrun()

CompositeAction = Task

class TwoParamAction(Action):
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

class FileCopyAction(TwoParamAction):
    def run(self):
        shutil.copy(self.src, self.dst)

    def __str__(self):
        return "COPY {0} -> {1}".format(self.src, self.dst)

class FileMoveAction(TwoParamAction):
    def run(self):
        shutil.move(self.src, self.dst)

    def __str__(self):
        return "MOVE {0} -> {1}".format(self.src, self.dst)

class FileRemoveAction(Action):
    def __init__(self, path):
        self.path = path

    def run(self):
        shutil.rmtree(self.path)

    def __str__(self):
        return "REMOVE {0}".format(self.src, self.dst)

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
            raise Exception(_i("This library created by stream"))

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
    @cached_property
    def filename(self):
        return fixfilename(self.name)



class Playlist(NameAccessMixin, dict):
    def __init__(self, lib, dic):
        self.lib = lib
        dict.__init__(self, dic)

    @cached_property
    def filename(self):
        return fixfilename(self.name)

    @cached_property
    def tracks(self):
        return list(self._collect_tracks())

    def _collect_tracks(self):
        try:
            items = self['Playlist Items']
        except KeyError:
            return []
        for track in self['Playlist Items']:
            try:
                track_id = track['Track ID']
                yield self.lib.track(track_id)
            except KeyError:
                warn(_i("Warning: Track ID {0} is not found in library").format(track_id))

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
            raise RuntimeError(os_name + _i(" is not supported."))

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
        return 'iTunes Library.xml'

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
        try:
            url = self.location
        except KeyError:
            raise IncompleteLibraryError(_i("Location of Track {} is not recorded on Library file.").format(self.name))
        return self.env.url_to_path(self.location)

    @cached_property
    def _stat(self):
        return os.stat(self.path)

    @cached_property
    def filesize(self):
        return self._stat.st_size

    def __getattr__(self, key):
        return getattr(self.track, key)

    def __str__(self):
        return "TrackAdapter<Track:{}, Env:{}>".format(self.track.name, type(self.env).__name__) # }}} # --------------------------------

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
        capability_file_pat = os.path.join(dev_dir, 'capability_*.xml')
        return len(glob.glob(capability_file_pat)) > 0

    def playlist_dirpath(self, playlist):
        return os.path.join(self.root_dir, 'MUSIC', playlist.filename)

    def __str__(self):
        return 'Walkman at {0}'.format(self.root_dir)

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
        self.submit(FileCopyAction(track.path, self.path))

    def update_track(self, track):
        if not os.path.exists(self.path) or\
                track.date_modified > self.last_modified:
            self.copy_track(track)

class VoidFile(VoidObject):
    pass


class SyncDirectory(WorkerMixin):
    RE_PAT = re.compile(r'\d+\s(.+)\.({})'.format(MUSICFILE_EXTENSIONS))
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
        debug('SyncDirectory {}: {}'.format(self.path, fs))
        return fs

    def update_track_at(self, track, pos):
        try:
            if track.filename in self.files_map:
                self.update_filename(track, pos)
            else:
                self.copy_new(track, pos)
        except IncompleteLibraryError as ex:
            error(ex)
            error(_i('We could not sync {} because it has incomplete information').format(track.name))

    def actual_name(self, track, pos):
        index = str(pos).zfill(self.index_digits)
        _, extension = os.path.splitext(track.path)
        return '{0} {1}{2}'.format(index, track.filename, extension)

    def actual_path(self, track, pos):
        name = self.actual_name(track, pos)
        return os.path.join(self.path, name)

    def update_filename(self, track, pos):
        newname = self.actual_name(track, pos)
        oldname = self.files_map[track.filename]
        if newname != oldname:
            self.move_file(oldname, newname)

    def move_file(self, oldname, newname):
        oldpath = os.path.join(self.path, oldname)
        newpath = os.path.join(self.path, newname)
        self.exec_move(oldpath, newpath)

    def exec_move(self, src, dst):
        self.submit(FileMoveAction(src, dst))

    def copy_new(self, track, pos):
        path = self.actual_path(track, pos)
        actual_file = ActualFile(path)
        actual_file.update_track(track)

    def create_actual_file(self, path):
        return ActualFile(path)

class LibrarySyncer(WorkerMixin):
    def __init__(self, library, config, device):
        self.library = library
        self.config = config
        self.device = device

    def sync(self, print_plan=True):
        if print_plan:
            self.print_plan()
        for playlist in self.target_playlists:
            dst_dir = self.targetdir(playlist)
            syncer = PlaylistSyncer(playlist, dst_dir)
            syncer.sync()

    def targetdir(self, playlist): # -> SyncDirectory
        dirpath = self.device.playlist_dirpath(playlist)
        return SyncDirectory(dirpath, len(playlist.tracks))

    @cached_property
    def target_playlists(self):
        return list(self.prepare_playlists())

    def prepare_playlists(self): # -> iter<Playlist>
        for pname, is_active in self.config.target_playlists.items():
            if not is_active:
                continue
            try:
                yield self.library.playlist_by_name(pname)
            except KeyError:
                warn(_i("Playlist {} was not found in library").format(pname))

    def print_plan(self, output=info):
        output(_i("LibrarySyncer at {}").format(self.library.path))
        output(_i("Following playlists will be synced"))
        for index, playlist in zipwithindex(self.target_playlists, start=1):
            output("{}: {}".format(index, playlist.name))

    start = sync

class DryLibrarySyncer(LibrarySyncer):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._inject_executor(DryExecutor())

class PlaylistSyncer(WorkerMixin):
    def __init__(self, playlist, dst_dir):
        """playlist: Playlist, dst_dir: SyncDirectory"""
        self.playlist = playlist
        self.targetdir = dst_dir

    def sync(self):
        tracks = self.playlist.tracks
        for index, track in zipwithindex(tracks, start=1):
            artist = track.get('artist', _i('<No artist>'))
            title  = track.get('name', _i('<No Title>'))
            info(_i("Syncing {}/{}").format(artist, title))
            self.targetdir.update_track_at(track, index)


# }}}
# --------------------------------

if __name__ == '__main__':
    m = Main()
    #m.config.inject(dry=True)
    m.start()

