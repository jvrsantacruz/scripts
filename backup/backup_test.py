#!/bin/env python
#-*- coding: utf-8 -*-

import os
import time
import shutil
import random
import doctest
import unittest
import subprocess
import random

import backup


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(backup))
    return tests


class TestDateFunctions(unittest.TestCase):
    def runTest(self):
        bktime = backup.get_copy_week(backup.get_copy_date())
        currtime = time.strftime(backup._WEEK_DATE_FMT_,
                                 time.strptime(backup.get_copy_date(),
                                               backup._COPY_DATE_FMT_))
        self.assertEqual(bktime, currtime)


class TestFormattingFunctions(unittest.TestCase):

    def setUp(self):
        self.user = 'user'
        self.host = '192.168.1.1'
        self.module = 'module'
        self.good_dates = [backup.get_copy_date()]
        self.dates = self.good_dates + ['20120000-1123']
        self.origins = ['/opt', '/usr/bin', '/home']
        self.ssh_origins = ['user@192.168.1.1:/opt',
                            'user@192.168.1.1:/usr/bin',
                            'user@192.168.1.1:/home']
        self.rsync_origins = ['192.168.1.1::module//opt',
                              '192.168.1.1::module//usr/bin',
                              '192.168.1.1::module//home']

        self.exclude_origins = ['--exclude', '/opt', '--exclude', '/usr/bin',
                             '--exclude', '/home']

    def test_get_ssh_origins(self):
        self.assertEqual(self.ssh_origins,
                         backup.get_ssh_origins(self.user,
                                                self.host,
                                                self.origins))

    def test_get_rsync_origins(self):
        self.assertEqual(self.rsync_origins,
                         backup.get_rsync_origins(self.module, self.host,
                                                  self.origins))

    def test_filter_copy_names(self):
        self.assertEqual(self.good_dates, backup.filter_copy_names(self.dates))

    def test_exclude_args(self):
        self.assertEqual(backup.format_exclude_args(self.origins),
                         self.exclude_origins)

    def test_syscall(self):
        self.assertEqual(subprocess.call(['ls'] + self.origins),
                        backup.syscall('ls', self.origins))

    def test_syscall_multiplearg(self):
        self.assertEqual(subprocess.call(['ls', '/home', '/opt']),
                        backup.syscall('ls', '/home', '/opt'))


def newfile(path, content="", randcontent=False):
    "Creates a new file with a given content"
    if randcontent:  # content is a string filled with random numbers
        content = str(random.randint(2 ** 1024, 2 ** 2048))

    with open(path, 'w') as dfile:
        dfile.write(content)


def find(root, name):
    "Returns paths ending in 'name' under root"
    for dirname, dirs, files in os.walk(root):
        if name in files + dirs:
            yield os.path.join(dirname, name)


def find_inodes(root, name=None):
    "Returns inodes for each file under root optionally ending in name"
    for dirname, dirs, files, in os.walk(root):
        for filename in files:
            if name is None or name == filename:
                yield os.stat(os.path.join(dirname, filename))


class TestFileOperations(unittest.TestCase):

    @staticmethod
    def get_copynames(n):
        "Generator for n random valid copy names"
        # Create 'copies'
        stamp = time.time()
        for hour in range(1, n + 1):
            date = time.strftime(backup._COPY_DATE_FMT_, time.localtime(stamp))
            stamp += 86400  # 1 more day
            yield date

    @staticmethod
    def newfile(path, content="", randcontent=False):
        "Creates a new file with a given content"
        if randcontent:  # content is a string filled with random numbers
            content = str(random.randint(2**1024, 2**2048))

        with open(path, 'w') as dfile:
            dfile.write(content)

    def setUp(self):
        """Create test directory enviroment
        The tree contains three directories with files that range all posibilities.
        File same-i: Same file (hard-linked) within the three directories.
        File dif-i: Different file (inode) but same contents within the three directories.
        File dif-i-content: Completely different file from all others. Unique.

        test
         |- 20120315-1422
         |   |- same-i          3045  (content: 'hello')
         |   |- dif-i           6777  (content: '11111..')
         |   `- dif-i-content   8423  (content: '24324..')
         |- 20120316-1422
         |   |- same-i          3045  (content: 'hello')
         |   |- dif-i           8797  (content: '11111..')
         |   `- dif-i-content   4233  (content: "87534..')
         `- 20120317-1422
             |- same-i          3045  (content: 'hello')
             |- dif-i           1234  (content: '11111..')
             `- dif-i-content   6327  (content: '78123..')
        """
        self.basepath = 'test'
        self.copynames = list(self.get_copynames(3))
        self.copypaths = [os.path.join(self.basepath, copy)
                          for copy in self.copynames]
        self.filenames = ['same-i', 'dif-i', 'dif-i-content']
        self.n_inodes = 7
        self.n_files = 9
        self.n_similar_files = 4
        self.n_diff_files = 5

        os.mkdir(self.basepath)
        for i, path in enumerate(self.copypaths):
            os.mkdir(path)

            if i == 0:
                newfile(os.path.join(path, 'same-i'), randcontent=True)
                shutil.copy(os.path.join(path, 'same-i'),
                            os.path.join(path, 'dif-i'))
                newfile(os.path.join(path, 'dif-i-content'), randcontent=True)
            else:
                # Unchanged file with same inode
                os.link(os.path.join(self.copypaths[i - 1], 'same-i'),
                        os.path.join(path, 'same-i'))
                # Unchanged file with different inode
                shutil.copy(os.path.join(self.copypaths[i - 1], 'dif-i'),
                           os.path.join(path, 'dif-i'))
                # Completely new file
                newfile(os.path.join(path, 'dif-i-content'),
                             randcontent=True)

        self.copyinodes = list(find_inodes(self.basepath, 'dif-i')) +\
                           list(find_inodes(self.basepath, 'same-i'))

    def tearDown(self):
        shutil.rmtree(self.basepath)

    def test_empty(self):
        pass


if __name__ == "__main__":
    unittest.main()
