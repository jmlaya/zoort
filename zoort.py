#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Mejorando.la - www.mejorando.la
# Yohan Graterol - <y@mejorando.la>

'''zoort

Usage:
  zoort backup <database> [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
  zoort backup <database> <user> <password> [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
  zoort backup <database> <user> <password> <host> [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
  zoort backup_all [--auth=<auth>] [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
  zoort download_all
  zoort decrypt <path>
  zoort configure
  zoort --version
  zoort --help

Options:
  -h --help           Show this screen.
  --version           Show version.
  --auth=<auth>       Only if it is necessary auth for dump.
  --path=<path>       Path target for the dump. [default: pwd].
  --upload_s3=<s3>    Upload to AWS S3 storage. [default: N].
  --encrypt=<encrypt> Encrypt output file dump before upload to S3. [default: Y]
'''

from __future__ import unicode_literals, print_function
import json
import os
import datetime
import time
import dateutil.parser
import boto
import shutil
import ftplib
from boto.s3.key import Key
from docopt import docopt
from functools import wraps
from fabric.api import local, hide
from fabric.colors import blue, red, green
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker
Base = declarative_base()

try:
    input = raw_input
except NameError:
    pass

__version__ = '0.1.7'
__author__ = 'Yohan Graterol'
__license__ = 'MIT'

ADMIN_USER = None
ADMIN_PASSWORD = None
AWS_ACCESS_KEY = None
AWS_SECRET_KEY = None
AWS_BUCKET_NAME = None
AWS_VAULT_NAME = None
AWS_KEY_NAME = None
PASSWORD_FILE = None
DELETE_BACKUP = None
DELETE_WEEKS = None

# Can be loaded from an import, but I put here
# for simplicity.
_error_codes = {
    100: u'Error #00: Can\'t load config.',
    101: u'Error #01: Database is not define.',
    103: u'Error #03: Backup name is not defined.',
    104: u'Error #04: Bucket name is not defined.',
    105: u'Error #05: Path for dump is not dir.',
    106: u'Error #06: Path is not file.',
    107: u'Error #07: Storage provider is wrong!',
    108: u'Error #08: Configure error!',
    109: u'Error #09: Oh, you are not root user! :(',
    110: u'Error #10: Path for sqlite database is not defined!.',
    111: u'Error #11: Backup path is invalid.',
    112: u'Error #12: Unable to connect to {0}: {1}',
    113: u'Error #13: Can\'t create directory {0} in {1}: {2}',
    114: u'Error #14: Can\'t change directory to {0}: {1}',
    115: u'Error #15: Can\'t upload file {0} in {1}: {2}',
    116: u'Error #16: Can\'t delete file {0}: {1}',
    117: u'Error #17: Can\'t get file date {0}: {1}',
    200: u'Warning #00: Field is requerid!',
    201: u'Warning #01: Field Type is wrong!',
    300: u'Success #00: Zoort is configure :)'
}


def factory_uploader(type_uploader, *args, **kwargs):

    def get_diff_date(creation_date):
        '''
        Return the difference between backup's date and now
        '''
        now = int(time.time())
        format = '%m-%d-%Y %H:%M:%S'
        date_parser = dateutil.parser.parse(creation_date)
        # convert string date to '%m-%d-%Y %H:%M:%S' format
        cd_strf = date_parser.strftime(format)
        # convert '%m-%d-%Y %H:%M:%S' to time.struct_time
        cd_struct = time.strptime(cd_strf, format)
        # convert time.struct_time to seconds
        cd_time = int(time.mktime(cd_struct))

        return now - cd_time

    class AWSS3(object):

        def __init__(self, *args, **kwargs):
            super(AWSS3, self).__init__()
            self.__dict__.update(kwargs)

            if not self.name_backup:
                raise SystemExit(_error_codes.get(103))
            if not self.bucket_name:
                raise SystemExit(_error_codes.get(104))

            # Connect to S3
            self.conn = boto.connect_s3(AWS_ACCESS_KEY, AWS_SECRET_KEY)
            # Get the bucket
            self.bucket = self.conn.get_bucket(self.bucket_name)

        def upload(self):
            global AWS_KEY_NAME
            if not AWS_KEY_NAME:
                AWS_KEY_NAME = 'dump/'

            print(blue('Uploading file to S3...'))

            # Delete all backups of two weeks before
            self._delete(bucket=self.bucket)

            k = Key(self.bucket)

            s3_key = (normalize_path(AWS_KEY_NAME) + 'week-' +
                      str(datetime.datetime.now().isocalendar()[1]) +
                      '/' + self.name_backup.split('/')[-1])

            print(blue('Uploading {0} to {1}.'.format(self.name_backup,
                                                      s3_key)))
            k.key = s3_key
            k.set_contents_from_filename(self.name_backup)

        def _get_old_backups(self, bucket):
            ret = []
            dif = DELETE_WEEKS * 7 * 24 * 60

            for key in bucket.list():
                if get_diff_date(key.creation_date) >= dif:
                    ret.append(key)

            return ret

        def _delete(self, bucket):
            global DELETE_BACKUP

            if not DELETE_BACKUP:
                return

            for key in self._get_old_backups(bucket):
                key.delete()

    class AWSGlacier(object):

        class File(Base):
            __tablename__ = 'file'

            id = Column(Integer, primary_key=True)
            date_upload = Column(String)
            filename = Column(String)
            archive_id = Column(String)

            def __init__(self, date_upload, filename, archive_id):
                self.date_upload = date_upload
                self.filename = filename
                self.archive_id = archive_id

            def __repr__(self):
                return "<File('%s','%s', '%s')>" % (self.date_upload,
                                                    self.filename,
                                                    self.archive_id)

        File.__table__

        File.__mapper__

        def __init__(self, *args, **kwargs):
            super(AWSGlacier, self).__init__()
            self.__dict__.update(kwargs)
            self.path = kwargs.get('path', None)
            self.name_backup = kwargs.get('name_backup', None)
            self.glacier_connection = \
                boto.connect_glacier(aws_access_key_id=AWS_ACCESS_KEY,
                                     aws_secret_access_key=AWS_SECRET_KEY)
            self.vault = self.glacier_connection.get_vault(AWS_VAULT_NAME)

        def connect_db(self):
            if not self.path:
                raise SystemExit(110)
            self.engine = create_engine('sqlite:///{0}'.format(self.path))
            Base.metadata.create_all(self.engine)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()

        def commit(self):
            self.session.dirty
            self.session.new
            self.session.commit()

        def add_archive_id(self, archiveID):
            archive_data = self.File(str(time.time()),
                                     self.name_backup,
                                     archiveID)
            self.session.add(archive_data)

        def get_file_from_time(self, time_old):
            return self.session.query(
                self.File).filter(self.File.date_upload<=time_old)

        def download_all_backups(self):
            jobs = self.vault.list_jobs(completed=True)
            for job in jobs:
                print(green('Downloading {0}'.format(job)))
                if job.description:
                    job.download_to_file(job.description)

        def upload(self):
            self.connect_db()
            if not self.name_backup:
                raise SystemExit(111)

            print(green('Uploading file to Glacier...'))
            archive_id = self.vault.upload_archive(
                self.name_backup, description=self.name_backup.split('/')[-1])
            retrieve_job = self.vault.retrieve_archive(archive_id)
            print(green('The job {0} is begin...'.format(retrieve_job)))
            self.add_archive_id(archive_id)
            self.delete()
            self.commit()

        def delete(self):
            print(green("Checking old backups..."))
            dif = time.time() - DELETE_WEEKS * 7 * 24 * 60 * 60
            archive_id_set = self.get_file_from_time(dif)
            for archive in archive_id_set:
                print(red('Deleting {0}...'.format(archive[0])))
                self.vault.delete_archive(archive[0])
                self.session.delete(archive)
                self.session.flush()


    class FTP(object):
        
        def __init__(self, *args, **kwargs):
            super(FTP, self).__init__()
            self.__dict__.update(kwargs)
            config_data = get_config_json()

            self.host = kwargs.get('host', 
                        config_data.get('ftp').get('host'))
            self.user = kwargs.get('user', 
                        config_data.get('ftp').get('user'))
            self.passwd = kwargs.get('passwd', 
                        config_data.get('ftp').get('passwd'))
            self.path = normalize_path(kwargs.get('path', \
                        config_data.get('ftp').get('path')))

            self.name_backup = kwargs.get('name_backup', None)

            if not self.name_backup:
                raise SystemExit(_error_codes.get(103))
        
        
        def connect(self):
            try:
                self.conn = ftplib.FTP(self.host, self.user, self.passwd)
            except Exception, e:
                raise SystemExit(_error_codes.get(12).format(self.host, e))

            print('Connected to {0}'.format(self.host))

        
        def disconnect(self):
            self.conn.quit()


        def mkdir(self, dirname):
            try:
                self.conn.mkd(dirname)
            except Exception, e:
                raise SystemExit(_error_codes.get(13).
                                    format(dirname, self.conn.pwd(), e))


        def change_dir(self, dirname):
            try:
                self.conn.cwd(dirname)
            except Exception, e:
                raise SystemExit(_error_codes.get(14).format(dirname, e))

        
        def send_file(self, filename):
            try:
                backup_file = open(filename, 'rb')
                self.conn.storbinary('STOR ' + filename, backup_file)
            except Exception, e:
                raise SystemExit(_error_codes.get(15).
                                    format(filename, path, e))


        def delete_file(self, filename):
            try:
                self.conn.delete(filename)
            except Exception, e:
                raise SystemExit(_error_codes.get(16).format(filename, e))


        def get_file_date(self, filename):
            try:
                mdtm = self.conn.sendcmd('MDTM ' + filename)
            except Exception, e:
                raise SystemExit(_error_codes.get(17).format(filename, e))

            return mdtm[4:]


        def list_files(self):
            '''
            Return all files in the actual directory without '.' and '..'
            '''
            ret = []
            
            for path in self.conn.nlst():
                if path in ['.', '..']:
                    continue
                ret.append(path)

            return ret

        
        def goto_path(self, path):
            '''
            Change to 'path' directory or create if not exist
            '''
            try:
                self.conn.cwd(folder)
            except:
                self.change_dir('/')
                for folder in path.split('/'):
                    if not folder:
                        continue

                    if not folder in self.conn.nlst():
                        self.mkdir(folder)
                    
                    self.change_dir(folder)

        
        def upload(self):
            self.connect()
            
            path = normalize_path(self.path) + 'week-' \
                    + str(datetime.datetime.now().isocalendar()[1])
            self.goto_path(path)

            print('Uploading file to {0} in {1}'.format(self.host, self.conn.pwd()))
            name_backup = self.name_backup.split('/')[-1]
            self.send_file(name_backup)
            self.delete()

            self.disconnect()

        
        def delete(self):
            global DELETE_BACKUP

            if not DELETE_BACKUP:
                return

            for filename in self._get_old_backup():
                self.delete_file(filename)


        def _get_old_backup(self):
            global DELETE_WEEKS
            ret = []
            dif = DELETE_WEEKS * 7 * 24 * 60

            self.goto_path(self.path)

            for path in self.list_files():
                self.change_dir(path)

                for backup in self.list_files():
                    if get_diff_date(self.get_file_date(backup))  >= dif:
                        # Add full path of backup
                        ret.append(self.conn.pwd() + '/' + backup)
                
                self.change_dir('..')

            return ret


    uploaders = {'S3': AWSS3,
                 'Glacier': AWSGlacier,
                 'FTP': FTP}

    upload = uploaders.get(type_uploader)(*args, **kwargs)

    if not upload:
        raise SystemExit(_error_codes.get(107))

    action = kwargs.get('action')

    if action == 'upload':
        upload.upload()
    elif action == 'download':
        upload.download_all_backups()


def transform_type(value, typ=None):
    if not typ:
        return value
    try:
        return typ(value)
    except ValueError:
        print(red(_error_codes.get(201)))
        return


def get_input(msg, is_password=False, verify_type=None):
    import getpass
    if is_password:
        inp = getpass.getpass
    else:
        inp = input
    in_user = transform_type(inp(msg), verify_type)
    while not in_user:
        print(red(_error_codes.get(200)))
        in_user = transform_type(inp(msg), verify_type)
    return in_user


def get_config_json():
    try:
        config = open('/etc/zoort/config.json')
    except IOError:
        try:
            config = open(
                os.path.join(
                    os.path.expanduser('~'),
                    '.zoort/config.json'))
        except IOError:
            raise SystemExit(_error_codes.get(100))

    config_data = json.load(config)
    return config_data


def configure():
    print('''
    Zoort v-{0}
    Please fill all fields for configure Zoort.
    '''.format(__version__))
    # Check if is root user
    if os.geteuid() != 0:
        raise SystemExit(_error_codes.get(109))
    config_dict = dict()
    config_dict['admin_user'] = get_input('MongoDB User Admin: ')
    config_dict['admin_password'] = \
        get_input('MongoDB Password Admin (Is hidden): ', True)
    # Define dict to aws key
    config_dict['aws'] = dict()

    # AWS Variables
    config_dict['aws']['aws_access_key'] = \
        get_input('AWS Access Key (Is hidden): ', True)
    config_dict['aws']['aws_secret_key'] = \
        get_input('AWS Secret Key (Is hidden): ', True)

    try:
        if int(get_input('Do you want use Amazon Web Services S3? '
                         ' (1 - Yes / 0 - No): ', verify_type=int)):
            config_dict['aws']['aws_bucket_name'] = \
                get_input('AWS Bucket S3 name: ')
        if int(get_input('Do you want use Amazon Web Services Glacier? '
                         ' (1 - Yes / 0 - No): ', verify_type=int)):
            config_dict['aws']['aws_vault_name'] = \
                get_input('AWS Vault Glacier name: ')
        config_dict['aws']['aws_key_name'] = \
            get_input('Key name for backups file: ')
        config_dict['aws']['password_file'] = \
            get_input('Password for encrypt with AES (Is hidden): ', True)
        config_dict['delete_backup'] = \
            int(get_input('Do you want delete old backups? '
                          ' (1 - Yes / 0 - No): ', verify_type=int))
        if config_dict['delete_backup']:
            config_dict['delete_weeks'] = \
                get_input('When weeks before of backups do you want delete? '
                          '(Number please) ', verify_type=int)
    except ValueError:
        raise SystemExit(_error_codes.get(108))

    with open('/etc/zoort/config.json', 'w') as config:
        json.dump(config_dict, config)
    print(green(_error_codes.get(300)))


def load_config(func):
    '''
    @Decorator
    Load config from JSON file.
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        config_data = get_config_json()
        try:
            global ADMIN_USER
            global ADMIN_PASSWORD
            global AWS_ACCESS_KEY
            global AWS_SECRET_KEY
            global AWS_BUCKET_NAME
            global AWS_VAULT_NAME
            global AWS_KEY_NAME
            global PASSWORD_FILE
            global DELETE_BACKUP
            global DELETE_WEEKS
            ADMIN_USER = config_data.get('admin_user')
            ADMIN_PASSWORD = config_data.get('admin_password')
            PASSWORD_FILE = config_data.get('password_file')
            AWS_ACCESS_KEY = config_data.get('aws').get('aws_access_key')
            AWS_SECRET_KEY = config_data.get('aws').get('aws_secret_key')
            AWS_BUCKET_NAME = config_data.get('aws').get('aws_bucket_name')
            AWS_VAULT_NAME = config_data.get('aws').get('aws_vault_name')
            AWS_KEY_NAME = config_data.get('aws').get('aws_key_name')
            DELETE_BACKUP = config_data.get('delete_backup')
            DELETE_WEEKS = config_data.get('delete_weeks')
        except ValueError:
            pass
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
        raise SystemExit(_error_codes.get(105))
    name_out_file = ('dump-' +
                     datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
    tar = tarfile.open(name_out_file + '.tar.gz', 'w:gz')
    tar.add(path, arcname='dump')
    tar.close()
    return (name_out_file, name_out_file + '.tar.gz')


def encrypt_file(path, output, password=None):
    '''
    Encrypt file with AES method and password.
    '''
    global PASSWORD_FILE
    if not password:
        password = PASSWORD_FILE
    query = 'openssl aes-128-cbc -salt -in {0} -out {1} -k {2}'
    with hide('output'):
        local(query.format(path, output, password))
        os.remove(path)


def decrypt_file(path, password=None):
    '''
    Decrypt file with AES method and password.
    '''
    global PASSWORD_FILE
    if not password:
        password = PASSWORD_FILE
    if path and not os.path.isfile(path):
        raise SystemExit(_error_codes.get(106))
    query = 'openssl aes-128-cbc -d -salt -in {0} -out {1} -k {2}'
    with hide('output'):
        local(query.format(path, path + '.tar.gz', PASSWORD_FILE))


def optional_actions(encrypt, path, compress_file, **kwargs):
    '''
    Optional actions about of AWS S3 and encrypt file.
    '''
    yes = ('y', 'Y')
    file_to_upload = normalize_path(path) + compress_file[1]
    if encrypt in yes:
        encrypt_file(normalize_path(path) + compress_file[1],
                     normalize_path(path) + compress_file[0])
        file_to_upload = normalize_path(path) + compress_file[0]

    if kwargs.get('s3') in yes:
        factory_uploader('S3', name_backup=file_to_upload,
                         bucket_name=AWS_BUCKET_NAME, action='upload')

    if kwargs.get('glacier') in yes:
        factory_uploader('Glacier', name_backup=file_to_upload,
                         vault_name=AWS_VAULT_NAME,
                         path=os.path.join(os.path.expanduser('~'),
                                           '.zoort.db'),
                         action='upload')


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
    if args.get('configure'):
        configure()
    if args.get('download_all'):
        download_all()


def download_all():
    factory_uploader('Glacier', action='download')


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
    glacier = args.get('--upload_glacier')
    encrypt = args.get('--encrypt') or 'Y'

    if not database:
        raise SystemExit(_error_codes.get(101))
    if path and not os.path.isdir(path):
        raise SystemExit(_error_codes.get(105))

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

    shutil.rmtree(normalize_path(path) + 'dump')

    optional_actions(encrypt, path, compress_file, s3=s3, glacier=glacier)


def backup_all(args):
    '''
    Backup all databases with access user.
    '''
    username = None
    password = None
    auth = args.get('--auth')
    path = args.get('--path') or os.getcwd()
    s3 = args.get('--upload_s3')
    glacier = args.get('--upload_glacier')
    encrypt = args.get('--encrypt') or 'Y'

    if (ADMIN_USER and ADMIN_PASSWORD):
        username = ADMIN_USER
        password = ADMIN_PASSWORD
    if path and not os.path.isdir(path):
        raise SystemExit(_error_codes.get(105))

    if auth:
        query = 'mongodump -u {username} -p {password} '
    else:
        query = 'mongodump '
    if path:
        query += '-o {path}/dump'

    local(query.format(username=username,
                       password=password,
                       path=path))

    compress_file = compress_folder_dump(normalize_path(path) + 'dump')

    shutil.rmtree(normalize_path(path) + 'dump')

    optional_actions(encrypt, path, compress_file, s3=s3, glacier=glacier)


if __name__ == '__main__':
    main()
