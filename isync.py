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
    'ja_JP': {
        "A simple synchronizer between iTunes and Walkman": "ちょっとしたiTunesとWalkman同期ソフト",
        "Python 3.3 or above required.": "Python 3.3以上をインストールして下さい。",
        "Reading configurations...": "設定を読み込んでいます・・・・",
        "Unable to read configuration, creating new one.": "設定ファイルを読み込めませんでした。新規に作成し続行します。",
        "Searching device...": "デバイスを探しています・・・",
        "No suitable device found.": "対応しているデバイスが見つかりませんでした",
        "Multi suitable devices found.  I will use {0} for syncing.": "複数の対応するデバイスが見つかりました。{0}を使用します。",
        "I will use {} for syncing": "{} を同期します",
        "No iTunes library found.": "iTuensライブラリが見つかりませんでした",
        "Path to config file": "設定ファイルへのパス",
        "Dry-run mode.": "Dry-runモード",
        "Verbose output. Set logging level to DEBUG": "詳細出力モード。loggingのレベルをDEBUGへ設定します",
        "Set logging level, default is WARN, overwrites \"-v\" option": "loggingのレベルを設定します。デフォルトはWARNです。これを設定すると\"-v\"オプションによるloggingの設定を上書きします",
        "<Path to iTunes Libaray.xml>": "<iTunes ライブラリへのパス>",
        "<Playlist Name>": "<プレイリスト名>",
        "Copying {} -> {}": "コピー中 {} -> {}",
        "Moving {} -> {}": "移動中 {} -> {}",
        "Removing {}": "削除中 {}",
        "This library created by stream": "ストリームから作成されたライブラリでは実行できません。",
        "Warning: Track ID {0} is not found in library": "警告: トラックID{0}はデータベースから見つかりませんでした。データベースが破損しています",
        " is not supported.": "はサポートされていません",
        "Track path of {} was recorded at iTunes library but musicfile is not found at the path, so I guess {} is a correct file.": "トラック {} の場所はiTunes Libraryに記録されていましたが、その場所にファイルはありませんでした。 それらしいファイル{}を発見したので、それを同期します",
        "Invalid location of Track {} was recorded on Library file.": "iTunesライブラリ上の {} のファイルパスが存在しない場所を指しています",
        "Track path of {} was not recorded at iTunes library but I guess {} is a correct file.": "トラック {} の場所はiTunes Libraryに記録されていませんでした。 それらしいファイル{}を発見したので、それを同期します",
        "Location of Track {} is not recorded on Library file.": "トラック {} の場所はiTunes Libraryに記録されていませんでした。",
        "Track '{}' will be moved from {} to {}": "トラック {} は {} から {} へ移動されます",
        "Track '{}' will be copied from {} to {}": "トラック {} は {} から {} へコピーされます",
        "File {} will be removed.": "トラック {} は削除されます",
        "Track '{}' has nothing to do.": "トラック {} は変更されません",
        "An error occurred during syncing {}: {}": "{} を同期中にエラーが発生しました: {}",
        "We could not sync {} because it has incomplete information": "ライブラリが不完全なため、{} を同期できませんでした",
        "Playlist {} was not found in library": "設定ファイルに誤りがあります。プレイリスト「{}」はライブラリ中に存在しません。",
        "Following playlists will be synced": "以下のプレイリストが同期されます",
        "<No artist>": "<アーティスト無し>",
        "<No Title>": "<タイトル無し>",
        "Multi suitable devices found. I will use {0} for syncing.": "複数の使用可能デバイスが見つかりました、{0}を使用します",
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
SYSTEM_PLAYLISTS = set(['Libaray', 'ライブラリ'])
DEBUG_MODE = False
MUSICFILE_EXTENSIONS = ['mp3', 'm4a', 'm4p']

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
import threading
import unicodedata
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
        self.execute()
        if self.env.is_win:
            input()  # pause console for cmd.exe

    def execute(self):
        try:
            # Check config file
            self.config
            self.sync()
        except FileNotFoundError as e:
            Config.prepare_default(self.library)
            warn(_i("Unable to read configuration, creating new one."))
            warn(_i("Please edit {0} and re-exec this app.")\
                 .format(self.args.config or DEFAULT_CONFIG_FILENAME))


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
            cfg = Config.load(self.args, path)
            cfg.logging_level = self._logging_level # set logging level
            return cfg
        except Exception as e:
            warn(e)
            raise e

    @cached_property
    def device(self):
        info(_i("Searching device..."))
        devices = list(DeviceLocator(self.env, self.config).find_all())
        if len(devices) < 1:
            self.abort(_i("No suitable device found."))
        elif len(devices) > 1 and\
            len(list(dev for dev in devices if not dev.is_fallback)) > 1:
            warn(_i("Multi suitable devices found.  I will use {0} for \
syncing.").format(devices[0]))
        info(_i("I will use {} for syncing").format(devices[0].root_dir))
        return devices[0]

    @cached_property
    def library(self):
        try:
            return Library(self.env.itunes_libfile())
        except Exception as e:
            error(e)
            self.abort(_i("No iTunes library found."))

    # DO NOT refer any attributes except 'args' to make sense of
    # logging.basicConfig
    def _init_logger(self):
        lvl = logging.INFO
        fmt = '%(levelname)-5s %(message)s'
        if ('verbose' in self.args and self.args.verbose) or DEBUG_MODE:
            lvl = logging.DEBUG
            fmt = '%(asctime)-15s %(levelname)-5s %(message)s'
        if 'logging' in self.args:
            lvl = getattr(logging, self.args.logging.upper())
        logging.basicConfig(level=lvl, format=fmt)
        self._logging_level = lvl

    def abort(self, *args):
        print(*args, file=sys.stderr)
        sys.exit(-1)


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
                            help=_i('Verbose output. \
Set logging level to DEBUG'))
        parser.add_argument('-t', '--target', metavar='DIR',
                            nargs='?', help='Sync target directory')
        parser.add_argument('--logging',
                            nargs='?', choices=['ERROR',
                                                'WARN',
                                                'INFO',
                                                'DEBUG'],
                            help=_i('Set logging level, \
default is WARN, overwrites "-v" option'))
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
        self.logging_level = logging.INFO

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
            'library_path': _i("<Path to iTunes Libaray.xml>"),
            'target_playlists': {_i('<Playlist Name>'): False},
            'force_update': False,
            'keep_removed_files': False,
        }
        cfg = Config(dic, VoidObject())
        if library is not None:
            cfg._inject_libaray(library)
        cfg.save()

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
        if name.startswith('_'):  # Ignore attribute starts with '_'
            return getattr(super(), name)
        ename = self._convert_name(name)
        return self[ename]

    def __hasattr__(self, key):
        ename = self._convert_name(key)
        return ename in self

    def get(self, key, default=None):
        ename = self._convert_name(key)
        if ename in self:
            return self[ename]
        else:
            return default

    def _convert_name(self, name):
        try:
            return NameAccessMixin.__name_mem[name]
        except KeyError:
            if name.startswith('is_'):
                name = name[3:]  # remove 'is_'
            converted_name = \
                    NameAccessMixin.__name_mem[name] = \
                    ' '.join(list(map(str.capitalize, name.split('_'))))
            return converted_name
        except AttributeError:
            NameAccessMixin.__name_mem = {}
            return self._convert_name(name)


def fixfilename(name):
    return FilenameFixer.instance.filter(name)


InvalidFilePathChars = set(list(iter('"<>|:*?\\/'))
                           + list(map(chr, range(0, 31))))


class FilenameFixer:
    def filter(self, expr):
        return ''.join(self._filter_invalid_dirname(expr))

    def _filter_invalid_dirname(self, name):
        return filter(lambda c: c not in InvalidFilePathChars, name)

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
        self._task_queue = queue.Queue()
        self.is_stopped = False
        self.__lock = threading.RLock()  # reentrant lock

    def start(self):
        with self.__lock:
            self.is_stopped = False
            self._flush_tasks()

    def _flush_tasks(self):
        while not self._task_queue.empty():
            f, args, kw = self._task_queue.get()
            self.worker.submit(f, *args, **kw)

    @property
    def worker(self):
        with self.__lock:
            try:
                return self._worker
            except AttributeError:
                self._worker = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1)
                return self._worker

    def submit(self, f, *args, **kw):
        with self.__lock:
            if self.is_stopped:
                self._task_queue.put((f, args, kw))
            else:
                self.worker.submit(f, *args, **kw)

    def stop(self):
        with self.__lock:
            if not self.is_stopped:
                self.worker.shutdown()
                del self._worker
                self.is_stopped = True

    shutdown = stop


class ExecutorSuspender:
    def __init__(self, executor):
        self.executor = executor

    def __enter__(self):
        self.executor.stop()

    def __exit__(self, ext_type, ext_val, ext_tb):
        self.executor.start()


class DryExecutor(Executor):
    def submit(self, f, *args, **kw):
        try:
            return super().submit(f.dryrun, *args, **kw)
        except AttributeError:
            info("DRYRUN: Submitting {}".format(repr(f)))


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


def event(*args, **kw):
    return EventProvider(*args, **kw)


class EventProvider:
    def __init__(self, doc=None):
        self.__doc__ = doc
        self._objects = {}

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            return self._objects[obj]
        except KeyError:
            handler = self._objects[obj] = Event(self, obj)
            return handler

    def __set__(self, obj, value):
        pass


class Event:
    def __init__(self, provider, target):
        self._provider = provider
        self._target = target
        self.handlers = []
        self.__handlers_lock = threading.RLock()

    def fire(self, *args, **kw):
        with self.__handlers_lock:
            for h in self.handlers:
                h(*args, **kw)

    def subscribe(self, f):
        with self.__handlers_lock:
            self.handlers.append(f)

    def unsubscribe(self, f):
        with self.__handlers_lock:
            self.handlers.remove(f)

    __call__ = fire
    __iadd__ = subscribe
    __isub__ = unsubscribe

class Action:
    is_atomic = False
    is_dry = False
    on_completed = event()

    def start(self, *args, dry=False, **kw):
        if self.is_dry or dry:
            self.dryrun(*args, **kw)
        else:
            self.run(*args, **kw)
        self.on_completed(*args, **kw)

    __call__ = start

    def dryrun(self, print_into=True):
        if print_into:
            debug(str(self))

    def run(self):
        pass


class VoidAction(Action):
    instance = Action()
    def __new__(cls):
        return VoidAction.instance


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
        info(_i("Copying {} -> {}").format(self.src, self.dst))
        shutil.copy(self.src, self.dst)

    def __str__(self):
        return "COPY {0} -> {1}".format(self.src, self.dst)


class FileMoveAction(TwoParamAction):
    def run(self):
        info(_i("Moving {} -> {}").format(self.src, self.dst))
        shutil.move(self.src, self.dst)

    def __str__(self):
        return "MOVE {0} -> {1}".format(self.src, self.dst)


class FileRemoveAction(Action):
    def __init__(self, path):
        self.path = path

    def run(self):
        info(_i("Removing {}").format(self.path))
        os.remove(self.path)

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
        return (lambda track: EnvTrackAdapter(Track(track), env))


class Track(NameAccessMixin, dict):
    @cached_property
    def filename(self):
        return fixfilename(self.name)

    def __str__(self):
        return "{}/{}".format(self.name, self.artist)


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
                warn(_i("Warning: Track ID {0} is not found in library")
                     .format(track_id))

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
        return super().url_to_path(path)[1:]  # Remove first /(slash)

    def devicedirs(self):
        for charcode in range(ord('D'), ord('Z') + 1):
            yield chr(charcode) + ":"

class TrackFinder:
    def __init__(self, track, env):
        self.track = track
        self.env = env

    def find_artistdir(self):
        candidate = os.path.join(
            self.env.itunes_dir(),
            'iTunes Media',
            'Music',
            self.track.artist_dirname)
        if os.path.isdir(candidate):
            return candidate

    def find_albumdir(self, artistdir):
        candidate = os.path.join(
            artistdir,
            self.track.album_dirname)
        if os.path.isdir(candidate):
            return candidate

    def find_track(self, albumdir):
        for af in ActualFile.glob(albumdir):
            if af.track_name == self.track.filename:
                return af

    def find(self):
        artistdir = self.find_artistdir()
        if artistdir is not None:
            albumdir = self.find_albumdir(artistdir)
            if albumdir is not None:
                return self.find_track(albumdir)


class EnvTrackAdapter:
    def __init__(self, track, env):
        self.track = track
        self.env = env

    @property
    def artist_dirname(self):
        if self.track.get('compilation', False):
            return 'Compilations'
        else:
            return fixfilename(self.artist)

    @property
    def album_dirname(self):
        return fixfilename(self.album)

    def _findfile_missing(self):
        finder = TrackFinder(self, self.env)
        guessed_file = finder.find()
        if guessed_file is not None:
            warn(_i("Track path of {} was recorded \
at iTunes library but musicfile is not found at \
the path, so I guess {} is a correct file.")\
                 .format(self.track, guessed_file.path))
            return guessed_file.path
        else:
            raise IncompleteLibraryError(
                _i("Invalid location of Track {} was recorded on Library file.")
                .format(self.name))

    def _findfile_fallback(self):
        finder = TrackFinder(self, self.env)
        guessed_file = finder.find()
        if guessed_file is not None:
            warn(_i("Track path of {} was not recorded \
at iTunes library but I guess {} \
is a correct file.").format(self.track, guessed_file.path))
            return guessed_file.path
        else:
            raise IncompleteLibraryError(
                _i("Location of Track {} is not recorded on Library file.")
                .format(self.name))

    @cached_property
    def path(self):
        try:
            path = self.env.url_to_path(self.location)
            if os.path.isfile(path):
                return path
            else:
                return self._findfile_missing()
        except KeyError: # Location has not been recorded on iTunes Library
            return self._findfile_fallback()
        except Exception as e:
            error(e)
            return None # Fixme: Return any other value


    @cached_property
    def _stat(self):
        return os.stat(self.path)

    @cached_property
    def filesize(self):
        return self._stat.st_size

    def __getattr__(self, key):
        return getattr(self.track, key)

    def __str__(self):
        return "TrackAdapter<Track:{}, Env:{}>"\
            .format(self.track.name, type(self.env).__name__)
# }}} # --------------------------------


# --------------------------------
#  Device Definitions {{{
# --------------------------------
class Device:
    is_fallback = False

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


class SyncTargetDir(Device):
    is_fallback = True
    def __init__(self, root_dir):
        self.root_dir = root_dir

    @staticmethod
    def is_suitable(path):
        return os.path.isdir(path)

    def playlist_dirpath(self, playlist):
        return os.path.join(self.root_dir, playlist.filename)

    def __str__(self):
        return 'SyncTargetDir at {}'.format(self.root_dir)

# }}}
# --------------------------------


# --------------------------------
#  Sync executors {{{
# --------------------------------
class DeviceLocator:
    def __init__(self, env, cfg):
        self.env = env
        self.config = cfg

    def devices(self):  # -> list<Device>
        return [Walkman]

    def suitables(self, dev_dir):  # -> iter<Device>
        return (
            dev(dev_dir) for dev in self.devices()
            if dev.is_suitable(dev_dir))

    def _device_candidates(self):
        yield from self.env.devicedirs()

    def find_all(self):  # -> iter<Devices>
        for dev_dir in self._device_candidates():
            yield from self.suitables(dev_dir)
        if 'target' in self.config:
            yield SyncTargetDir(self.config.target)


class ActualFile(WorkerMixin):
    RE_FILENAME = re.compile(r'(\d+)\s(.+)\.({})'.format('|'.join(MUSICFILE_EXTENSIONS)))
    def __init__(self, path):
        """path: indexed file path"""
        self.path = unicodedata.normalize('NFC', path)

    @staticmethod
    def glob(dirpath):
        return (ActualFile(os.path.join(dirpath, fname))
                for fname in os.listdir(dirpath))

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
            return WillBeCopied(track, self.path)
        else:
            return NothingToDo(track)

    @cached_property
    def filename(self):
        return os.path.basename(self.path)

    @cached_property
    def _matched(self):
        return self.RE_FILENAME.match(self.filename)

    @property
    def track_number(self):
        return int(self._matched.group(1))

    @property
    def track_name(self):
        return self._matched.group(2)

    @property
    def extension(self):
        return self._matched.group(3)


class VoidFile(VoidObject):
    pass


# -----------------------------------
# SyncPlan
# -----------------------------------
class SyncPlan:
    importance = logging.INFO


class WillBeRenamed(SyncPlan):
    def __init__(self, track, oldpath, newpath):
        self.track = track
        self.oldpath = oldpath
        self.newpath = newpath

    def __str__(self):
        return _i("Track '{}' will be moved from {} to {}")\
                .format(self.track.name, self.oldpath, self.newpath)


class WillBeCopied(SyncPlan):
    def __init__(self, track, path):
        self.track = track
        self.path = path

    def __str__(self):
        return _i("Track '{}' will be copied from {} to {}")\
                .format(self.track.name, self.track.path, self.path)


class WillBeDeleted(SyncPlan):
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return _i("File {} will be removed.")\
                .format(self.path)


class NothingToDo(SyncPlan):
    importance = logging.DEBUG

    def __init__(self, track):
        self.track = track

    def __str__(self):
        return _i("Track '{}' has nothing to do.")\
                .format(self.track.name)


class AnErrorOccurrd(SyncPlan):
    importance = logging.ERROR

    def __init__(self, track, ex):
        self.track = track
        self.exception = ex

    def __str__(self):
        return _i("An error occurred during syncing {}: {}")\
                .format(self.track.name, self.exception)

# -----------------------------------

class SyncDirectory(WorkerMixin):
    RE_PAT = re.compile(r'\d+\s(.+)\.({})'.format(MUSICFILE_EXTENSIONS))

    def __init__(self, path, expected_files_count,
                 force_write=False, dryrun=False):
        self.path = path
        self.files_map = self.collect_files()
        self.force_write = force_write
        self.index_digits = int(math.log10(expected_files_count)) + 1

    def collect_files(self):  # -> dict<str, str>
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        fs = {}
        for af in ActualFile.glob(self.path):
            fs[af.track_name] = af
        return fs

    def prune_tracks(self, tracks):  # generator of SyncPlan
        fm = {}  # Track.filename -> Track
        for track in tracks:
            fm[track.filename] = track
        for track_name, af in self.files_map.items():
            if track_name not in fm:
                yield self.remove_track(af.path)

    def remove_track(self, path):
        self.submit(FileRemoveAction(path))
        return WillBeDeleted(path)

    def update_track_at(self, track, pos):
        try:
            if track.filename in self.files_map:
                return self.update_filename(track, pos)
            else:
                return self.copy_new(track, pos)
        except IncompleteLibraryError as ex:
            error(ex)
            error(_i('We could not sync {} because it has incomplete \
information').format(track.name))
            return AnErrorOccurrd(track, ex)

    def actual_name(self, track, pos):
        index = str(pos).zfill(self.index_digits)
        if track.path is None:
            raise IncompleteLibraryError()
        _, extension = os.path.splitext(track.path)
        return '{0} {1}{2}'.format(index, track.filename, extension)

    def actual_path(self, track, pos):
        name = self.actual_name(track, pos)
        return os.path.join(self.path, name)

    def update_filename(self, track, pos):
        newname = self.actual_name(track, pos)
        oldname = self.files_map[track.filename].filename
        if newname != oldname:
            self.move_file(oldname, newname)
            return WillBeRenamed(track, oldname, newname)
        else:
            return NothingToDo(track)

    def move_file(self, oldname, newname):
        oldpath = os.path.join(self.path, oldname)
        newpath = os.path.join(self.path, newname)
        self.exec_move(oldpath, newpath)

    def exec_move(self, src, dst):
        self.submit(FileMoveAction(src, dst))

    def copy_new(self, track, pos):
        path = self.actual_path(track, pos)
        actual_file = ActualFile(path)
        return actual_file.update_track(track)

    def create_actual_file(self, path):
        return ActualFile(path)


class SyncerManager(WorkerMixin):
    def __init__(self, libsyncer):
        self.libsyncer = libsyncer

    def start(self):
        with ExecutorSuspender(self._executor):
            libsyncaction = self.libsyncer.sync(print_plan=False)


class LibrarySyncer(WorkerMixin):
    def __init__(self, library, config, device):
        self.library = library
        self.config = config
        self.device = device

    def sync(self, print_plan=True):
        with ExecutorSuspender(self._executor):
            playlist_actions = self._sync_playlists()  # Eager evaluation
            if print_plan:
                self.print_plan(playlist_actions)

    def _sync_playlists(self):
        for playlist in self.target_playlists:
            dst_dir = self.targetdir(playlist)
            syncer = PlaylistSyncer(playlist, dst_dir)
            yield from syncer.sync()

    def targetdir(self, playlist):  # -> SyncDirectory
        dirpath = self.device.playlist_dirpath(playlist)
        return SyncDirectory(dirpath, len(playlist.tracks))

    @cached_property
    def target_playlists(self):
        return list(self.prepare_playlists())

    def prepare_playlists(self):  # -> iter<Playlist>
        for pname, is_active in self.config.target_playlists.items():
            if not is_active:
                continue
            try:
                yield self.library.playlist_by_name(pname)
            except KeyError:
                warn(_i("Playlist {} was not found in library").format(pname))

    def print_plan(self, actions, output=info):
        output(_i("Following playlists will be synced"))
        for index, playlist in zipwithindex(self.target_playlists, start=1):
            output("{}: {}".format(index, playlist.name))
        logging_level = self.config.logging_level
        for action in actions:
            if action.importance > logging_level:
                output(action)

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
        yield from self.targetdir.prune_tracks(tracks)
        for index, track in zipwithindex(tracks, start=1):
            artist = track.get('artist', _i('<No artist>'))
            title = track.get('name', _i('<No Title>'))
            yield self.targetdir.update_track_at(track, index)


# }}}
# --------------------------------

if __name__ == '__main__':
    m = Main()
    #m.config.inject(dry=True)
    m.start()
