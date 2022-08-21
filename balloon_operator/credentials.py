#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Credential administration for Balloon Operator.

Copyright (C) 2022 Andreas Schneider <andreas.schneider@fmi.fi>

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

import keyring

service_id = 'balloon_operator'

def storePassword(service, username, password):
    """
    Store a password in the system keyring.
    """
    keyring.set_password(service_id+'/'+service, username, password)

def getPassword(service, username):
    """
    Retrieve a password from the system keyring.
    """
    return keyring.get_password(service_id+'/'+service, username)

if __name__ == '__main__':
    import argparse
    import getpass
    parser = argparse.ArgumentParser('Credential administration for Balloon Operator')
    parser.add_argument('-e', '--email', help='store email password in system keyring (give username as parameter)')
    parser.add_argument('-r', '--rockblock', help='store RockBLOCK password in system keyring (give username as parameter)')
    parser.add_argument('-w', '--webserver', help='store webserver password in system keyring (give username as parameter)')
    args = parser.parse_args()
    if args.email:
        password = getpass.getpass(prompt='Email password: ')
        storePassword('email', args.email, password)
    if args.rockblock:
        password = getpass.getpass(prompt='RockBLOCK password: ')
        storePassword('rockblock', args.rockblock, password)
    if args.webserver:
        password = getpass.getpass(prompt='Webserver password: ')
        storePassword('webserver', args.webserver, password)
