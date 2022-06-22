#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module to handle messages via externally modified local files.

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

import numpy as np
import datetime
import os
from balloon_operator import message


class MessageFile(message.Message):
    """
    Receive data from payload via local file (e.g. generated by external
    proprietary software)

    Expected format: one tsv ASCII line.
    """

    def __init__(self, filename, delimiter='\t', datetime_format='%Y-%m-%dT%H:%M:%S',
                 fieldnames=['DATETIME', 'LON', 'LAT', 'ALT', 'PRESS', 'TEMP', 'HUMID']):
        """
        Constructor.
        @param filename: filename to be monitored
        @param delimiter tsv delimiter (default: '\t')
        datetime, longitude, latitude, altitude, presure, temperature, humidity
        The file may contrain only first 4 5, 6, or 7 of these entries.
        """
        super().__init__()
        self.filename = filename
        self.timestamp = None
        self.delimiter = delimiter
        self.datetime_format=datetime_format
        self.fieldnames = fieldnames
        # urllib.parse.urlparse

    def decodeMessage(self, msg):
        """
        Parse file.

        @param msg received message
        @return data data of parsed message in form of a dictionary
        """
        fields = msg.split(self.delimiter)
        data = {}
        for ind in range(len(fields)):
            if self.fieldnames[ind] == 'DATETIME':
                data[self.fieldnames[ind]] = datetime.datetime.strptime(fields[ind], self.datetime_format)
            else:
                data[self.fieldnames[ind]] = float(fields[ind])
        return data

    def encodeMessage(self, data):
        """
        Encode file.

        @param data dictionary containing data to be included in file
        @return msg encoded message
        """
        raise NotImplementedError

    def receiveMessage(self):
        """
        Read message from file if it has changed.
        """
        stamp = os.stat(self.filename).st_mtime
        if stamp != self.timestamp:
            self.timestamp = stamp
            with open(self.filename, 'r') as fd:
                line = fd.readline()
            if line.endswith('\n'):
                line = line[:-1]
            return line
        else:
            return None

    def receiveMessages(self):
        """
        Return a list of new message(s).
        """
        msg = self.receiveMessage()
        if msg is None:
            return []
        else:
            return [msg]

    def connect(self, **kwargs):
        """
        Connect to endpoint. Nothing to be done.
        """
        return

    def disconnect(self):
        """
        Disconnect from endpoint. Nothing to be done.
        """
        return

    def isConnected(self):
        """
        Check if instance is connected to an endpoint.
        Always the case for a local file.
        """
        return True


def fromSettings(settings):
    """
    Create a MessageFile instance from settings.
    """
    return MessageFile(
            settings['file']['path'],
            delimiter=settings['file']['delimiter'] if 'delimiter' in settings['file'] else '\t',
            datetime_format=settings['file']['datetime_format'] if 'datetime_format' in settings['file'] else '%Y-%m-%dT%H:%M:%S')

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('file', required=False, default=None, help='File name with messages')
    args = parser.parse_args()
    message_handler = MessageFile(args.file)
    print(message_handler.decodeMessage(message_handler.receiveMessage()))
