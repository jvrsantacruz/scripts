#!/bin/env python
#-*- coding: utf-8 -*-

import doctest
import unittest
import time
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


if __name__ == "__main__":
    unittest.main()
