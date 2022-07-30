#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abstract interface for messages received from and sent to the balloon payload.

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
import gpxpy
import gpxpy.gpx
import logging

class Message(object):
    """
    Interface for communication with balloon payload.
    """

    def decodeMessage(self, msg):
        """
        Parse message received from payload.
        To be implemented in child class.

        @param msg received (binary) message
        @return data data of parsed message in form of a dictionary
        """
        raise NotImplementedError

    def encodeMessage(self, data):
        """
        Encode message to be sent to payload.
        To be implemented in child class.

        @param data dictionary containing data to be included in message
        @return msg encoded message
        """
        raise NotImplementedError

    def receiveMessage(self):
        """
        Receive a message from payload.
        To be implemented in child class.

        @return msg received message, or None if no new message is available
        """
        raise NotImplementedError

    def receiveMessages(self):
        """
        Receive all available new messages from payload.
        To be implemented in child class.

        @return msg_list a list of messages (empty list if no message is available)
        """
        raise NotImplementedError

    def sendMessage(self, msg):
        """
        Send message to payload.
        To be implemented in child class.

        @param msg encode (binary) message
        """
        raise NotImplementedError

    def getDecodedMessages(self, **kwargs):
        """
        Get a list of parsed messages.

        @param kwargs keyword arguments handed on to receiveMessages()
    
        @return messages translated messages
        """
        msg_list = []
        raw_msg_list = self.receiveMessages(**kwargs)
        for raw_msg in raw_msg_list:
            try:
                msg_list.append(self.decodeMessage(raw_msg))
            except (ValueError, AssertionError) as err:
                logging.error('Error decoding message: {}'.format(err))
                pass
        return msg_list

    @staticmethod
    def sortMessages(messages):
        """
        Sort a list of messages according to time.

        @param messages a list of messages

        @return messages sorted list of messages
        """
        if len(messages) == 0:
            return messages
        msg_time = [msg['DATETIME'] for msg in messages]
        idx_sort = np.argsort(msg_time)
        if (idx_sort != np.arange(len(messages))).any():
            logging.info('Sorting messages according to time: {}'.format(idx_sort))
            messages = np.array(messages)[idx_sort]
        return messages

    def connect(self, **kwargs):
        """
        Connect to endpoint.
        To be implemented in child class.
        """
        raise NotImplementedError

    def disconnect(self):
        """
        Disconnect from endpoint.
        To be implemented in child class.
        """
        raise NotImplementedError

    def isConnected(self):
        """
        Check if instance is connected to an endpoint.
        To be implemented in child class.
        """
        raise NotImplementedError

    @staticmethod
    def message2trackpoint(msg):
        """
        Creates a GPX trackpoint from a parsed message.
    
        @param msg dictionary with parsed message
    
        @return pkt GPX trackpoint corresponding to message data
        """
        return gpxpy.gpx.GPXTrackPoint(
                    msg['LAT'], msg['LON'], elevation=msg['ALT'], time=msg['DATETIME'],
                    comment='{} hPa'.format(msg['PRESS']) if 'PRESS' in msg else None)

    @staticmethod
    def message2waypoint(msg, name='Current'):
        """
        Creates a GPX waypoint from a parsed message.
    
        @param msg parsed message
        @param name name of the waypoint (default: 'Current')
    
        @return pkt GPX waypoint corresponding to message data
        """
        status_text = ''
        if 'PRESS' in msg:
            status_text += 'Pressure: {} hPa\n'.format(msg['PRESS'])
        if 'TEMP' in msg:
            status_text += 'Temperature: {:.1f} °C\n'.format(msg['TEMP'])
        if 'HUMID' in msg:
            status_text += 'Humidity: {:.1f} %\n'.format(msg['HUMID'])
        if 'BATTV' in msg:
            status_text += 'Battery: {:.2f} V\n'.format(msg['BATTV'])
        pkt = gpxpy.gpx.GPXWaypoint(
            msg['LAT'], msg['LON'], elevation=msg['ALT'], time=msg['DATETIME'],
            name=name, description=status_text)
        return pkt
