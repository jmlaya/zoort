#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Mejorando.la - www.mejorando.la
# Yohan Graterol - <y@mejorando.la>

'''zoort

Usage:
  zoort backup <database> [--path=<path>] [--upload_s3=<s3>] [--encrypt=<encrypt>]
  zoort backup <database> <user> <password> [--path=<path>] [--upload_s3=<s3>] [--encrypt=<encrypt>]
  zoort backup <database> <user> <password> <host> [--path=<path>] [--upload_s3=<s3>] [--encrypt=<encrypt>]
  zoort backup_all <user_admin> <password_admin> [--path=<path>] [--upload_s3=<s3>] [--encrypt=<encrypt>]
  zoort decrypt <path>
  zoort --version
  zoort --help

Options:
  -h --help           Show this screen.
  --version           Show version.
  --path=<path>       Path target for the dump. [default: pwd].
  --upload_s3=<s3>    Upload to AWS S3 storage. [default: N].
  --encrypt=<encrypt> Encrypt output file dump before upload to S3. [default: Y]
'''

from __future__ import unicode_literals, print_function
import json
import os
import datetime
import boto
from boto.s3.key import Key
from docopt import docopt
from functools import wraps
from fabric.api import local, hide
from fabric.colors import blue

__version__ = '0.1.0'
__author__ = 'Yohan Graterol'
__license__ = 'MIT'

ADMIN_USER = None
ADMIN_PASSWORD = None
AWS_ACCESS_KEY = None
AWS_SECRET_KEY = None
AWS_BUCKET_NAME = None
AWS_KEY_NAME = None
PASSWORD_FILE = None


def load_config(func):
    '''
    @Decorator
    Load config from JSON file.
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        config = None
        try:
            config = open('/etc/zoort/config.json')
        except IOError:
            try:
                config = open(
                    os.path.join(
                        os.path.expanduser('~'),
                        '.zoort/config.json'))
            except IOError:
                raise SystemExit('Error #00: Can\'t load config.')
        config_data = json.load(config)

        global ADMIN_USER
        global ADMIN_PASSWORD
        global AWS_ACCESS_KEY
        global AWS_SECRET_KEY
        global AWS_BUCKET_NAME
        global AWS_KEY_NAME
        global PASSWORD_FILE
        ADMIN_USER = config_data.get('admin_user')
        ADMIN_PASSWORD = config_data.get('admin_password')
        PASSWORD_FILE = config_data.get('password_file')
        AWS_ACCESS_KEY = config_data.get('aws').get('aws_access_key')
        AWS_SECRET_KEY = config_data.get('aws').get('aws_secret_key')
        AWS_BUCKET_NAME = config_data.get('aws').get('aws_bucket_name')
        AWS_KEY_NAME = config_data.get('aws').get('aws_key_name')
        return func(*args, **kwargs)
    return wrapper


def normalize_path(path):
    '''
    Add slash to path end
    '''
    if path[-1] != '/':
        return path + '/'
    return path


def compress_folder_dump(path):
    '''
    Compress folder dump to tar.gz file
    '''
    import tarfile
    if not path or not os.path.isdir(path):
        raise SystemExit('Error #05: Path for dump is not dir.')
    name_out_file = ('dump-' +
                     datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
    tar = tarfile.open(name_out_file + '.tar.gz', 'w:gz')
    tar.add(path, arcname='dump')
    tar.close()
    return (name_out_file, name_out_file + '.tar.gz')


def encrypt_file(path, output):
    '''
    Encrypt file with AES method and password.
    '''
    global PASSWORD_FILE
    query = 'openssl aes-128-cbc -salt -in {0} -out {1} -k {2}'
    with hide('output'):
        local(query.format(path, output, PASSWORD_FILE))
        os.remove(path)


def decrypt_file(path):
    '''
    Decrypt file with AES method and password.
    '''
    global PASSWORD_FILE
    if path and not os.path.isfile(path):
        raise SystemExit('Error #06: Path is not file.')
    query = 'openssl aes-128-cbc -d -salt -in {0} -out {1} -k {2}'
    with hide('output'):
        local(query.format(path, path + '.tar.gz', PASSWORD_FILE))


def optional_actions(encrypt, s3, path, compress_file):
    '''
    Optional actions about of AWS S3 and encrypt file.
    '''
    yes = ('y', 'Y')
    file_to_upload = normalize_path(path) + compress_file[1]
    if encrypt in yes:
        encrypt_file(normalize_path(path) + compress_file[1],
                     normalize_path(path) + compress_file[0])
        file_to_upload = normalize_path(path) + compress_file[0]
    if s3 in yes:
        upload_backup(file_to_upload, AWS_BUCKET_NAME)


@load_config
def main():
    '''Main entry point for the mongo_backups CLI.'''
    args = docopt(__doc__, version=__version__)
    if args.get('backup'):
        backup_database(args)
    if args.get('backup_all'):
        backup_all(args)
    if args.get('decrypt'):
        decrypt_file(args.get('<path>'))


def backup_database(args):
    '''
    Backup one database from CLI
    '''
    username = args.get('<user>')
    password = args.get('<password>')
    database = args['<database>']
    host = args.get('<host>') or '127.0.0.1'
    path = args.get('[--path]') or os.getcwd()
    s3 = args.get('--upload_s3')
    encrypt = args.get('--encrypt') or 'Y'

    if not database:
        raise SystemExit('Error #01: Database is not define.')
    if path and not os.path.isdir(path):
        raise SystemExit('Error #05: Path for dump is not dir.')

    if (ADMIN_USER and ADMIN_PASSWORD) and not username or not password:
        username = ADMIN_USER
        password = ADMIN_PASSWORD

    query = 'mongodump -d {database} --host {host} '
    if username:
        query += '-u {username} '
    if password:
        query += '-p {password} '
    if path:
        query += '-o {path}/dump'

    local(query.format(username=username,
                       password=password,
                       database=database,
                       host=host,
                       path=path))
    compress_file = compress_folder_dump(normalize_path(path) + 'dump')

    optional_actions(encrypt, s3, path, compress_file)


def backup_all(args):
    '''
    Backup all databases with access user.
    '''
    username = args.get('<user_admin>')
    password = args.get('<password_admin>')
    path = args.get('[--path]') or os.getcwd()
    s3 = args.get('--upload_s3')
    encrypt = args.get('--encrypt') or 'Y'

    if not username or not password:
        raise SystemExit('Error #02: User or password for '
                         'admin is not defined.')
    if path and not os.path.isdir(path):
        raise SystemExit('Error #05: Path for dump is not dir.')

    query = 'mongodump -u {username} -p {password} '

    if path:
        query += '-o {path}/dump'

    local(query.format(username=username,
                       password=password,
                       path=path))
    compress_file = compress_folder_dump(normalize_path(path) + 'dump')

    optional_actions(encrypt, s3, path, compress_file)


def delete_old_backups(bucket,
                       week=str(datetime.datetime.now().isocalendar()[1] - 2)):
    for key in bucket.list(prefix=normalize_path(AWS_KEY_NAME) +
                           'week-' + week):
        key.delete()


def upload_backup(name_backup=None, bucket_name=None):
    global AWS_KEY_NAME
    if not name_backup:
        raise SystemExit('Error #03: Backup name is not defined.')
    if not bucket_name:
        raise SystemExit('Error #04: Bucket name is not defined.')
    print(blue('Uploading file to S3...'))
    # Connect to S3
    conn = boto.connect_s3(AWS_ACCESS_KEY, AWS_SECRET_KEY)
    # Get the bucket
    bucket = conn.get_bucket(bucket_name)
    # Delete all backups of two weeks before
    delete_old_backups(bucket=bucket)
    k = Key(bucket)
    if not AWS_KEY_NAME:
        AWS_KEY_NAME = 'mongodb/'
    s3_key = (normalize_path(AWS_KEY_NAME) + 'week-' +
              str(datetime.datetime.now().isocalendar()[1]) +
              '/' + name_backup.split('/')[-1])
    print(blue('Uploading {0} to {1}.'.format(name_backup, s3_key)))
    k.key = s3_key
    k.set_contents_from_filename(name_backup)


if __name__ == '__main__':
    main()
