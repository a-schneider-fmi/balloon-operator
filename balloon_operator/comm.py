#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 24 11:00:04 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import io
import os.path

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
