===============================
 Zoort
===============================

.. image:: https://mejorando.la/static/images/logos/mejorandola.png
        :target: https://www.mejorando.la

.. image:: https://badge.fury.io/py/zoort.png
    :target: http://badge.fury.io/py/zoort

.. image:: https://pypip.in/d/zoort/badge.png
        :target: https://crate.io/packages/zoort?version=latest

A Python script for automatic MongoDB backups

Features
--------

* Backup for just one or all your MongoDB Databases.
* Encrypt and Decrypt output dump file.
* Upload file to S3 bucket.

Requirements
------------

- Python 2.6 | 2.7

Usage
-------

::
    zoort backup <database> [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
    zoort backup <database> <user> <password> [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
    zoort backup <database> <user> <password> <host> [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
    zoort backup_all [--auth=<auth>] [--path=<path>] [--upload_s3=<s3>] [--upload_glacier=<glacier>] [--encrypt=<encrypt>]
    zoort download_all
    zoort decrypt <path>
    zoort configure
    zoort --version
    zoort --help 


License
-------

MIT licensed. See the bundled `LICENSE <https://github.com/yograterol/zoort/blob/master/LICENSE>`_ file for more details.