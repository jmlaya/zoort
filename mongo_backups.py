#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Mejorando.la - www.mejorando.la
# Yohan Graterol - <y@mejorando.la>

'''mongo_backups

Usage:
  mongo_backups backup <database> [path]
  mongo_backups backup <database> <user> <password> [path]
  mongo_backups backup <database> <user> <password> <host> [path]
  mongo_backups backup_all <user_admin> <password_admin> [path]
  mongo_backups -h | --help
  mongo_backups --version

Options:
  -h --help     Show this screen.
  --version     Show version.
  --speed=<kn>  Speed in knots [default: 10].
  --moored      Moored (anchored) mine.
  --drifting    Drifting mine.
'''

from __future__ import unicode_literals, print_function
from docopt import docopt
from fabric.api import local

__version__ = "0.1.0"
__author__ = "Yohan Graterol"
__license__ = "MIT"


def main():
    '''Main entry point for the mongo_backups CLI.'''
    args = docopt(__doc__, version=__version__)
    print(args)
    if args.get("backup"):
        backup_database(args)
    if args.get("backup_all"):
        backup_all(args)


def backup_database(args):
    username = args.get('<user>') or None
    password = args.get('<password>') or None
    database = args['<database>']
    host = args.get('<host>') or '127.0.0.1'
    path = args.get('[path]') or None

    if not database:
        raise SystemExit('Error #01: Database is not define.')

    query = 'mongodump -d {database} --host {host}'
    if username:
        query += '-u {username} '
    if password:
        query += '-p {password}'
    if path:
        query += '-o {path}'

    local(query.format(username=username,
                       password=password,
                       database=database,
                       host=host,
                       path=path))


def backup_all(args):
    username = args.get('<user_admin>') or None
    password = args.get('<password_admin>') or None
    path = args.get('[path]') or None

    if not username or not password:
        raise SystemExit('Error #02: User or password for '
                         'admin is not defined.')

    query = 'mongodump -u {username} -p {password}'

    if path:
        query += '-o {path}'

    local(query.format(username=username,
                       password=password,
                       path=path))


if __name__ == '__main__':
    main()
