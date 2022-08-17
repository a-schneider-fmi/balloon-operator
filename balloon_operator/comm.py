#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module for communication with external servers using various protocols.

Copyright (C) 2021, 2022 Andreas Schneider <andreas.schneider@fmi.fi>

This file is part of Balloon Operator.

Balloon Operator is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

Balloon Operator is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Balloon Operator. If not, see <https://www.gnu.org/licenses/>.
"""

import io
import os.path
import configparser
import tempfile
from balloon_operator import message_sbd, message_file

def uploadFtp(server_settings, filename, bio):
    """
    Upload content to FTP server.
    """
    import ftplib
    ftp = ftplib.FTP(server_settings['host'])
    ftp.login(user=server_settings['user'], passwd=server_settings['password'])
    ftp.cwd(server_settings['directory'])
    ftp.storbinary('STOR '+filename, bio)
    ftp.close()
    return


def uploadSftp(server_settings, filename, bio):
    """
    Upload content via scp/sftp.
    """
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
    ssh.connect(
            server_settings['host'], username=server_settings['user'], 
            password=server_settings['password'] if 'password' in server_settings else None,
            look_for_keys=True, allow_agent=True)
    sftp = ssh.open_sftp()
    sftp.putfo(bio, os.path.join(server_settings['directory'], filename))
    sftp.close()
    ssh.close()
    return


def uploadPost(server_settings, filename, contents):
    """
    Upload content via http post.
    """
    import requests
    resp = requests.post(
            server_settings['host'],
            data={'token': server_settings['password']},
            files={'fileToUpload': (filename, contents)})
    print(resp.ok, resp.text) # DEBUG
    return


def uploadFile(server_settings, filename, contents):
    """
    Upload contents from string to file on server.
    """
    try:
        contents = contents.encode('utf-8')
    except (AttributeError, UnicodeEncodeError):
        pass
    bio = io.BytesIO(contents) # Create file-like object from contents.
    if server_settings['protocol'].lower() == 'ftp':
        uploadFtp(server_settings, filename, bio)
    elif server_settings['protocol'].lower() == 'sftp':
        uploadSftp(server_settings, filename, bio)
    elif server_settings['protocol'].lower() == 'post':
        uploadPost(server_settings, filename, contents)
    else:
        print('Unknown protocol: {}'.format(server_settings['protocol']))
    return


def readCommSettings(filename):
    """
    Load communication settings from an ini file.
    """
    settings = {
            'connection': {
                    'type': 'rockblock',
                    'poll_time': 30
                    },
            'email': {
                    'host': None,
                    'user': None,
                    'password': None,
                    'old_ssl': False,
                    'from': '@rockblock.rock7.com'
                    },
            'rockblock': {
                    'user': None,
                    'password': None
                    },
            'file': {
                    'path': None,
                    'delimiter': '\t'
                    },
            'webserver': {
                    'protocol': None,
                    'host': None,
                    'user': None,
                    'password': None,
                    'directory': None,
                    'webpage': None,
                    'networklink': None,
                    'refreshinterval': None
                    },
            'output': {
                    'format': 'gpx',
                    'filename': 'trajectory.kml',
                    'directory': tempfile.gettempdir()
                    },
            'geofence': {
                    'radius': 0.
                    }
            }
    config = configparser.ConfigParser()
    config.read(filename)
    for section in config.sections():
        if section not in settings:
            settings[section] = {}
        for option in config.options(section):
            if option in settings[section]: # if a default value exists
                default_value = settings[section][option]
            else:
                default_value = None
            if isinstance(default_value,float):
                settings[section][option] = config[section].getfloat(option)
            elif isinstance(default_value,int):
                settings[section][option] = config[section].getint(option)
            elif isinstance(default_value,bool):
                settings[section][option] = config[section].getboolean(option)
            else:
                settings[section][option] = config[section].get(option)
    return settings


def messageHandlerFromSettings(settings):
    """
    Create a Message object corresponding to the given settings.
    """
    if settings['connection']['type'] == 'rockblock':
        if settings['email']['host'] is None or settings['email']['user'] is None or settings['email']['password'] is None:
            raise ValueError('Reception connection set to rockblock, but no complete email configuration is present.')
        message_handler = message_sbd.fromSettings(settings)
    elif settings['connection']['type'] == 'file':
        message_handler = message_file.fromSettings(settings)
        if settings['file']['path'] is None:
            raise ValueError('Reception connection set to file, but no file path is given.')
    else:
        raise ValueError('Unknown connection type: {}'.format(settings['connection']['type']))
    return message_handler
