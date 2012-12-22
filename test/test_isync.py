
from nose.tools import *

import isync
import os
import shutil
import sys
import io

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
    @property
    def target_playlists(self):
        return [ 'A Playlist' ]

class TestLibrarySyncer:
    def setup(self):
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
        assert_file_exists(DEVICEDIR, 'A Playlist', '0 TuneDelta.mp3')

    def test_update(self):
        lib1 = isync.Library(create_library('testlib.xml'))
        dev1 = isync.Walkman(DEVICEDIR)
        cfg1 = DummyPlaylists()
        syncer1 = isync.LibrarySyncer(lib1, cfg1, dev1)
        syncer1.sync()
        lib2 = isync.Library(create_library('testlib2.xml'))
        dev2 = isync.Walkman(DEVICEDIR)
        cfg2 = DummyPlaylists()
        syncer2 = isync.LibrarySyncer(lib2, cfg2, dev2)
        syncer2.sync()
        assert_file_exists(DEVICEDIR, 'A Playlist', '0 TuneAlpha.mp3')
        assert_file_exists(DEVICEDIR, 'A Playlist', '1 TuneDelta.mp3')


class TestAlterableFn:
    pass

