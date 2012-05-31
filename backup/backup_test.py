#!/bin/env python
#-*- coding: utf-8 -*-

import os
import time
import shutil
import random
import doctest
import unittest
import subprocess

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

    def test_filter_date_names(self):
        self.assertEqual(self.good_dates, backup.filter_date_names(self.dates,
                                                       backup._COPY_DATE_FMT_))

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
                yield os.stat(os.path.join(dirname, filename)).st_ino


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

    def test_check(self):
        "Tests check command's output"
        output = subprocess.check_output(['./backup.py', '-v', '--dest',
                                          self.basepath, 'check'])

        # Check present files
        prev_inodes = list(find_inodes(self.basepath))
        self.assertEqual(len(prev_inodes), self.n_files)
        self.assertEqual(len(set(prev_inodes)), self.n_inodes)

        #self.assertTrue('Same content in {0} different files of size'
        #                .format(self.n_similar_files) in output)

        #for inode in self.copyinodes:
        #    self.assertTrue('inode: {0}'.format(inode) in output)

        # Check files after operation. Should remain intact.
        current_inodes = list(find_inodes(self.basepath))
        self.assertEqual(len(current_inodes), self.n_files)
        self.assertEqual(len(set(current_inodes)), self.n_inodes)

    def test_check_repare(self):
        "Tests check repare command's side effects"
        prev_inodes = list(find_inodes(self.basepath))
        self.assertEqual(len(prev_inodes), self.n_files)
        self.assertEqual(len(set(prev_inodes)), self.n_inodes)

        # Execute command
        output = subprocess.check_output(['./backup.py', '--repare', '-v',
                                          '--dest', self.basepath, 'check'])

        # Check output
        #self.assertTrue('Unifying {0} files to one'\
        #        .format(self.n_similar_files) in output)
        #self.assertEqual(output.count('Removing repeated file '),
        #                   self.n_similar_files - 1)
        #self.assertEqual(output.count('Linking '),
        #                   self.n_similar_files - 1)
        #self.assertTrue('{0} files unified'.format(self.n_similar_files - 1)
        #                  in output)

        # Check that similar files has been merged
        current_inodes = list(find_inodes(self.basepath))
        self.assertEqual(len(current_inodes), self.n_files)
        self.assertTrue(len(set(current_inodes)), self.n_diff_files)


class TestBackup(unittest.TestCase):
    "Tests backup command"

    def setUp(self):
        """Creates a `copy` directory that holds certain files and a `backup`
        dir to copy to"""
        self.copy_path = './copy'
        self.file_name = 'file.txt'
        self.file_path = os.path.join(self.copy_path, self.file_name)
        self.copy_inner_path = os.path.join(self.copy_path, 'inner')
        self.file_inner_path = os.path.join(self.copy_inner_path, self.file_name)
        self.backup_path = './backup'
        self.backup_file_path = os.path.join(self.backup_path, self.file_path)
        self.backup_file_inner_path = os.path.join(self.backup_path, self.file_inner_path)

        os.mkdir(self.copy_path)
        os.mkdir(self.copy_inner_path)
        os.mkdir(self.backup_path)

        newfile(self.file_path, randcontent=True)
        newfile(self.file_inner_path, randcontent=True)

    def tearDown(self):
        shutil.rmtree(self.copy_path)
        shutil.rmtree(self.backup_path)

    def test_backup(self):
        "Tests basic backup"
        date = backup.get_copy_date()
        ret = subprocess.call(['./backup.py', '--origin', self.copy_path,
                               '--dest', self.backup_path, 'backup'])
        self.assertEqual(ret, 0)
        self.assertEqual(len(list(find(self.backup_path, date))), 1)
        self.assertEqual(len(list(find(self.backup_path, 'last'))), 1)
        self.assertEqual(len(list(find(self.backup_path, self.file_name))), 2)


if __name__ == "__main__":
    unittest.main()
