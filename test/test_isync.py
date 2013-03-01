
from nose.tools import *

import isync
import os
import shutil
import sys
import io
import logging

pjoin = os.path.join
APPROOT = os.path.abspath(pjoin(os.path.dirname(__file__), '../'))
TUNESDIR = pjoin(APPROOT, 'DummyTunes')
DEVICEDIR = pjoin(APPROOT, 'DummyDevDir')
TESTDIR = pjoin(APPROOT, 'test')

def touch(*paths, body=""):
    with open(os.path.join(*paths), 'w') as f:
        f.write(body)

def prepare_tunedir():
    if not os.path.exists(TUNESDIR):
        os.mkdir(TUNESDIR)
    files = ['TuneAlpha.mp3', 'TuneBravo.mp3']
    for tunename in files:
        touch(TUNESDIR, tunename, body='DummyFile {0}'.format(tunename))

def prepare_dummy_walkmandir():
    if not os.path.exists(DEVICEDIR):
        os.mkdir(DEVICEDIR)
    touch(DEVICEDIR, 'capability_00.xml', body="foobar")

def create_library(name):
    with open(pjoin(TESTDIR, name)) as f:
        rawstr = f.read()
        body = rawstr.format(TUNESDIR=TUNESDIR)
        return io.BytesIO(body.encode('utf-8'))

def assert_file_exists(*args):
    path = os.path.join(*args)
    ok_(os.path.exists(path), msg="{0} does not exists.".format(path))

@nottest
def remove_test_files():
    dirs = [TUNESDIR, DEVICEDIR]
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)

class ImmediateExecutor(isync.Executor):
    def submit(self, f, *args, **kw):
        return f(*args, **kw)

class TestLibrary:
    def test_lib(self):
        lib = isync.Library(create_library('testlib.xml'))
        pl = lib.playlist_by_name('A Playlist')
        assert_equals(pl.name, "A Playlist")
        assert_equals(1, len(pl.tracks))
        tr = lib.track(1368)
        assert_equals(tr.name, 'TuneAlpha')
        assert_equals(tr.album_artist, 'AlbumArtistBravo')
        assert_equals(tr.path, os.path.join(TUNESDIR, 'TuneAlpha.mp3'))


class TestWindows:
    def test_devicedirs(self):
        win = isync.Windows()
        assert_equals(list(win.devicedirs())[:3], ['D:', 'E:', 'F:'])
        assert_equals(list(win.devicedirs())[-1:], ['Z:'])

class DummyPlaylists:
    logging_level = logging.DEBUG
    @property
    def target_playlists(self):
        return { 'A Playlist' : True }

class TestLibrarySyncer:
    def setup(self):
        remove_test_files()
        prepare_tunedir()
        prepare_dummy_walkmandir()

    def teardown(self):
        remove_test_files()

    def test_sync(self):
        lib = isync.Library(create_library('testlib.xml'))
        dev = isync.Walkman(DEVICEDIR)
        cfg = DummyPlaylists()
        syncer = isync.LibrarySyncer(lib, cfg, dev)
        syncer.sync()
        syncer.shutdown()
        assert_file_exists(DEVICEDIR, 'MUSIC', 'A Playlist', '1 TuneDelta.mp3')

    def test_update(self):
        lib1 = isync.Library(create_library('testlib.xml'))
        dev1 = isync.Walkman(DEVICEDIR)
        cfg1 = DummyPlaylists()
        syncer1 = isync.LibrarySyncer(lib1, cfg1, dev1)
        syncer1._inject_executor(ImmediateExecutor())
        syncer1.sync()
        syncer1.shutdown()
        touch(TUNESDIR, '2 SomeTune.mp3', body='DummyFile SomeTune')
        lib2 = isync.Library(create_library('testlib2.xml'))
        dev2 = isync.Walkman(DEVICEDIR)
        cfg2 = DummyPlaylists()
        syncer2 = isync.LibrarySyncer(lib2, cfg2, dev2)
        syncer2._inject_executor(ImmediateExecutor())
        syncer2.sync()
        assert_file_exists(DEVICEDIR, 'MUSIC', 'A Playlist', '1 TuneAlpha.mp3')
        assert_file_exists(DEVICEDIR, 'MUSIC', 'A Playlist', '2 TuneDelta.mp3')


class DummyWorker(isync.WorkerMixin):
    def create_child(self):
        return DummyChildWorker()

class DummyChildWorker(isync.WorkerMixin):
    pass

class APlaneClass:
    def create_worker(self):
        return DummyChildWorker()

class TestWorker:
    def test_create(self):
        worker = isync.WorkerMixin()
        assert_equals(isync.ExecutorService.root.default, worker._executor)

    def test_inherit(self):
        parent_worker = DummyWorker()
        assert_equals(isync.ExecutorService.root.default, parent_worker._executor)
        parent_worker._executor = 1
        child_worker = parent_worker.create_child()
        assert_equals(child_worker._executor, parent_worker._executor)

    def test_create_in_plane(self):
        plane_class = APlaneClass()
        isync.ExecutorService.root.default = 100
        worker = plane_class.create_worker()
        assert_equals(100, worker._executor)

class TestCommandArguments:
    def test_parse(self):
        opts = isync.CommandArguments('--logging INFO -d'.split())
        ok_(opts.dry)
        assert_equals(opts.logging, 'INFO')

    def test_interface(self):
        opts = isync.CommandArguments(['-v'])
        ok_('verbose' in opts)
        ok_('logging' not in opts)

class EventHolder:
    on_foobar = isync.event()
    def fire(self, arg):
        self.on_foobar(arg)

class TestEvent:
    def setup(self):
        self.last_arg = None

    def test_event(self):
        target = EventHolder()
        target.on_foobar += self.handler_mock
        assert_equals(None, self.last_arg)
        target.fire(10)
        assert_equals(10, self.last_arg)
        target.on_foobar -= self.handler_mock  # unsubscribe
        target.fire(20)
        assert_equals(10, self.last_arg) # not called

    def handler_mock(self, arg):
        self.last_arg = arg

class TestActualFile:
    def test_filenameparse(self):
        af = isync.ActualFile('/Foobar/012 HogeHoge.mp3')
        assert_equals(12, af.track_number)
        assert_equals('HogeHoge', af.track_name)
        assert_equals('mp3', af.extension)


