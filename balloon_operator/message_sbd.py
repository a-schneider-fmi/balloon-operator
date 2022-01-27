#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Receive/send and decode/encode IRIDIUM SBD messages from RockBLOCK devices.

Created on Fri May  7 08:06:27 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

from enum import Enum
import numpy as np
import datetime
import struct
import gpxpy
import gpxpy.gpx
import configparser
import imaplib
import email
import requests
import os.path
import sys
import logging
from balloon_operator import message


class TrackerMessageFields(Enum):
    """
    Define message field IDs.
    Taken over from the binary message format of Sparkfun's Artemis Global Tracker.
    https://github.com/sparkfunX/Artemis_Global_Tracker/blob/master/Software/examples/Example16_GlobalTracker/Tracker_Message_Fields.h
    """
    STX       = 0x02
    ETX       = 0x03
    SWVER     = 0x04
    BATTC     = 0x07
    SOURCE    = 0x08
    BATTV     = 0x09
    PRESS     = 0x0a
    TEMP      = 0x0b
    HUMID     = 0x0c
    YEAR      = 0x0d
    MONTH     = 0x0e
    DAY       = 0x0f
    HOUR      = 0x10
    MIN       = 0x11
    SEC       = 0x12
    MILLIS    = 0x13
    DATETIME  = 0x14
    LAT       = 0x15
    LON       = 0x16
    ALT       = 0x17
    SPEED     = 0x18
    HEAD      = 0x19
    SATS      = 0x1a
    PDOP      = 0x1b
    FIX       = 0x1c
    GEOFSTAT  = 0x1d
    USERVAL1  = 0x20
    USERVAL2  = 0x21
    USERVAL3  = 0x22
    USERVAL4  = 0x23
    USERVAL5  = 0x24
    USERVAL6  = 0x25
    USERVAL7  = 0x26
    USERVAL8  = 0x27
    MOFIELDS  = 0x30
    FLAGS1    = 0x31
    FLAGS2    = 0x32
    DEST      = 0x33
    HIPRESS   = 0x34
    LOPRESS   = 0x35
    HITEMP    = 0x36
    LOTEMP    = 0x37
    HIHUMID   = 0x38
    LOHUMID   = 0x39
    GEOFNUM   = 0x3a
    GEOF1LAT  = 0x3b
    GEOF1LON  = 0x3c
    GEOF1RAD  = 0x3d
    GEOF2LAT  = 0x3e
    GEOF2LON  = 0x3f
    GEOF2RAD  = 0x40
    GEOF3LAT  = 0x41
    GEOF3LON  = 0x42
    GEOF3RAD  = 0x43
    GEOF4LAT  = 0x44
    GEOF4LON  = 0x45
    GEOF4RAD  = 0x46
    WAKEINT   = 0x47
    ALARMINT  = 0x48
    TXINT     = 0x49
    LOWBATT   = 0x4a
    DYNMODEL  = 0x4b
    RBHEAD    = 0x52
    USERFUNC1 = 0x58
    USERFUNC2 = 0x59
    USERFUNC3 = 0x5a
    USERFUNC4 = 0x5b
    USERFUNC5 = 0x5c
    USERFUNC6 = 0x5d
    USERFUNC7 = 0x5e
    USERFUNC8 = 0x5f  


class MessageSbd(message.Message):
    """
    Communication via Short Burst Data (SBD) with the Artemis Global Tracker
    or compatible devices.
    """

    """
    Define the type of the binary data fields.
    Either a dtype or a length in bytes for more complicated cases.
    Entries according to the binary message format of Sparkfun's Artemis Global Tracker.
    """
    FIELD_TYPE = {
            TrackerMessageFields.STX: 0,
            TrackerMessageFields.ETX: 0,
            TrackerMessageFields.SWVER: np.dtype('uint8'),
            TrackerMessageFields.BATTC: np.dtype('uint16'),
            TrackerMessageFields.SOURCE: np.dtype('uint32'),
            TrackerMessageFields.BATTV: np.dtype('uint16'),
            TrackerMessageFields.PRESS: np.dtype('uint16'),
            TrackerMessageFields.TEMP: np.dtype('int16'),
            TrackerMessageFields.HUMID: np.dtype('uint16'),
            TrackerMessageFields.YEAR: np.dtype('uint16'),
            TrackerMessageFields.MONTH: np.dtype('uint8'),
            TrackerMessageFields.DAY: np.dtype('uint8'),
            TrackerMessageFields.HOUR: np.dtype('uint8'),
            TrackerMessageFields.MIN: np.dtype('uint8'),
            TrackerMessageFields.SEC: np.dtype('uint8'),
            TrackerMessageFields.MILLIS: np.dtype('uint16'),
            TrackerMessageFields.DATETIME: 7,
            TrackerMessageFields.LAT: np.dtype('int32'),
            TrackerMessageFields.LON: np.dtype('int32'),
            TrackerMessageFields.ALT: np.dtype('int32'),
            TrackerMessageFields.SPEED: np.dtype('int32'),
            TrackerMessageFields.HEAD: np.dtype('int32'),
            TrackerMessageFields.SATS: np.dtype('uint8'),
            TrackerMessageFields.PDOP: np.dtype('uint16'),
            TrackerMessageFields.FIX: np.dtype('uint8'),
            TrackerMessageFields.GEOFSTAT: (np.dtype('uint8'), 3),
            TrackerMessageFields.USERVAL1: np.dtype('uint8'),
            TrackerMessageFields.USERVAL2: np.dtype('uint8'),
            TrackerMessageFields.USERVAL3: np.dtype('uint16'),
            TrackerMessageFields.USERVAL4: np.dtype('int16'),
            TrackerMessageFields.USERVAL5: np.dtype('uint32'),
            TrackerMessageFields.USERVAL6: np.dtype('uint32'),
            TrackerMessageFields.USERVAL7: np.dtype('float32'),
            TrackerMessageFields.USERVAL8: np.dtype('float32'),
            TrackerMessageFields.MOFIELDS: (np.dtype('uint32'), 3),
            TrackerMessageFields.FLAGS1: np.dtype('uint8'),
            TrackerMessageFields.FLAGS2: np.dtype('uint8'),
            TrackerMessageFields.DEST: np.dtype('uint32'),
            TrackerMessageFields.HIPRESS: np.dtype('uint16'),
            TrackerMessageFields.LOPRESS: np.dtype('uint16'),
            TrackerMessageFields.HITEMP: np.dtype('int16'),
            TrackerMessageFields.LOTEMP: np.dtype('int16'),
            TrackerMessageFields.HIHUMID: np.dtype('uint16'),
            TrackerMessageFields.LOHUMID: np.dtype('uint16'),
            TrackerMessageFields.GEOFNUM: np.dtype('uint8'),
            TrackerMessageFields.GEOF1LAT: np.dtype('int32'),
            TrackerMessageFields.GEOF1LON: np.dtype('int32'),
            TrackerMessageFields.GEOF1RAD: np.dtype('uint32'),
            TrackerMessageFields.GEOF2LAT: np.dtype('int32'),
            TrackerMessageFields.GEOF2LON: np.dtype('int32'),
            TrackerMessageFields.GEOF2RAD: np.dtype('uint32'),
            TrackerMessageFields.GEOF3LAT: np.dtype('int32'),
            TrackerMessageFields.GEOF3LON: np.dtype('int32'),
            TrackerMessageFields.GEOF3RAD: np.dtype('uint32'),
            TrackerMessageFields.GEOF4LAT: np.dtype('int32'),
            TrackerMessageFields.GEOF4LON: np.dtype('int32'),
            TrackerMessageFields.GEOF4RAD: np.dtype('uint32'),
            TrackerMessageFields.WAKEINT: np.dtype('uint32'),
            TrackerMessageFields.ALARMINT: np.dtype('uint16'),
            TrackerMessageFields.TXINT: np.dtype('uint16'),
            TrackerMessageFields.LOWBATT: np.dtype('uint16'),
            TrackerMessageFields.DYNMODEL: np.dtype('uint8'),
            TrackerMessageFields.RBHEAD: 4,
            TrackerMessageFields.USERFUNC1: 0,
            TrackerMessageFields.USERFUNC2: 0,
            TrackerMessageFields.USERFUNC3: 0,
            TrackerMessageFields.USERFUNC4: 0,
            TrackerMessageFields.USERFUNC5: np.dtype('uint16'),
            TrackerMessageFields.USERFUNC6: np.dtype('uint16'),
            TrackerMessageFields.USERFUNC7: np.dtype('uint32'),
            TrackerMessageFields.USERFUNC8: np.dtype('uint32')
    }
    
    """
    Conversion factors for data fields. Fields that do not appear in this list
    have a conversion factor of 1 (i.e. no conversion).
    Taken over from the documentation of Sparkfun's Artemis Global Tracker.
    """
    CONVERSION_FACTOR = {
            TrackerMessageFields.BATTC: 1e-3,
            TrackerMessageFields.BATTV: 1e-2,
            TrackerMessageFields.TEMP: 1e-2,
            TrackerMessageFields.HUMID: 1e-2,
            TrackerMessageFields.LAT: 1e-7,
            TrackerMessageFields.LON: 1e-7,
            TrackerMessageFields.ALT: 1e-3,
            TrackerMessageFields.HEAD: 1e-7,
            TrackerMessageFields.HITEMP: 1e-2,
            TrackerMessageFields.LOTEMP: 1e-2,
            TrackerMessageFields.HIHUMID: 1e-2,
            TrackerMessageFields.LOHUMID: 1e-2,
            TrackerMessageFields.GEOF1LAT: 1e-7,
            TrackerMessageFields.GEOF1LON: 1e-7,
            TrackerMessageFields.GEOF1RAD: 1e-2,
            TrackerMessageFields.GEOF2LAT: 1e-7,
            TrackerMessageFields.GEOF2LON: 1e-7,
            TrackerMessageFields.GEOF2RAD: 1e-2,
            TrackerMessageFields.GEOF3LAT: 1e-7,
            TrackerMessageFields.GEOF3LON: 1e-7,
            TrackerMessageFields.GEOF3RAD: 1e-2,
            TrackerMessageFields.GEOF4LAT: 1e-7,
            TrackerMessageFields.GEOF4LON: 1e-7,
            TrackerMessageFields.GEOF4RAD: 1e-2,
            TrackerMessageFields.LOWBATT: 1e-2
    }

    def __init__(self, email_host=None, email_user=None, email_password=None,
                 email_from='@rockblock.rock7.com',
                 rockblock_user=None, rockblock_password=None):
        """
        Constructor
        """
        super().__init__()
        self.imap = None
        self.email_host = email_host
        self.email_user = email_user
        self.email_password = email_password
        self.email_from = email_from
        self.rockblock_user = rockblock_user
        self.rockblock_password = rockblock_password

    @staticmethod
    def asc2bin(msg_asc):
        """
        Convert ASCII representation of binary message to real binary message.
        """
        msg = b''
        for ind in np.arange(0,len(msg_asc),2):
            msg += np.uint8(int(msg_asc[ind:ind+2], 16))
        return msg
    

    @staticmethod
    def bin2asc(msg_bin):
        """
        Encode binary message to ASCII representation.
        """
        msg_asc = ''
        for ind in range(len(msg_bin)):
            msg_asc += '{:02x}'.format(msg_bin[ind])
        return msg_asc


    @staticmethod
    def checksum(data):
        """
        Compute checksum bytes according to the 8-Bit Fletcher Algorithm.
    
        @param data byte array of data
    
        @return cs_a
        @return cs_b
        """
        old_settings = np.seterr(over='ignore') # Do not warn for desired overflow in this computation.
        cs_a = np.uint8(0)
        cs_b = np.uint8(0)
        for ind in range(len(data)):
            cs_a += np.uint8(data[ind])
            cs_b += cs_a
        np.seterr(**old_settings)
        return cs_a, cs_b


    def decodeMessage(self, msg):
        """
        Decode binary SBD message from Sparkfun Artemis Global Tracker.
    
        File format documented at https://github.com/sparkfunX/Artemis_Global_Tracker under
        * Documentation/Message_Format/README.md
        * Software/examples/Example16_GlobalTracker/Tracker_Message_Fields.h
    
        @param msg message as byte array
    
        @return data translated message as dictionary
        """
        data = {}
        if msg[0] == TrackerMessageFields.STX.value:
            ind = 0
        else: # assuming 
            ind = 5
        assert(msg[ind] == TrackerMessageFields.STX.value)
        ind += 1
        while (msg[ind] != TrackerMessageFields.ETX.value):
            field = TrackerMessageFields(msg[ind])
            ind += 1
            if isinstance(self.FIELD_TYPE[field], int): # length in bytes
                field_len = self.FIELD_TYPE[field]
                if field == TrackerMessageFields.DATETIME:
                    values = struct.unpack('HBBBBB', msg[ind:ind+field_len])
                    logging.debug('  DATETIME: {}'.format(values))
                    data[field.name] = datetime.datetime(*values)
                elif field_len > 0:
                    data[field.name] = msg[ind:ind+field_len]
                else:
                    data[field.name] = None
            elif isinstance(self.FIELD_TYPE[field], np.dtype): # dtype of scalar
                field_len = self.FIELD_TYPE[field].itemsize
                data[field.name] = np.frombuffer(msg[ind:ind+field_len], dtype=self.FIELD_TYPE[field])[0]
            elif isinstance(self.FIELD_TYPE[field], tuple): # dtype and length of array
                field_len = self.FIELD_TYPE[field][0].itemsize * self.FIELD_TYPE[field][1]
                data[field.name] = np.frombuffer(msg[ind:ind+field_len], dtype=self.FIELD_TYPE[field][0])
            else:
                raise ValueError('Unknown entry in FIELD_TYPE list: {}'.format(self.FIELD_TYPE[field]))
            if field in self.CONVERSION_FACTOR:
                data[field.name] = float(data[field.name]) * self.CONVERSION_FACTOR[field]
            ind += field_len
        ind += 1 # ETX
        cs_a, cs_b = self.checksum(msg[:ind])
        assert (msg[ind] == cs_a), 'Checksum mismatch'
        assert (msg[ind+1] == cs_b), 'Checksum mismatch'
        return data


    def encodeMessage(self, data):
        """
        Create a binary SBD message in Sparkfun Artemis Global Tracker format.
    
        @param data dictionary with data to send, with keys named according to TrackerMessageFields names
    
        @return msg encoded binary SBD message
        """
        msg = b''
        msg += np.uint8(TrackerMessageFields.STX.value)
        for field in TrackerMessageFields:
            if field.name in data:
                msg += np.uint8(field.value)
                if field == TrackerMessageFields.DATETIME:
                    msg += struct.pack(
                            'HBBBBB',
                            data[field.name].year, data[field.name].month,
                            data[field.name].day, data[field.name].hour,
                            data[field.name].minute, data[field.name].second)
                elif isinstance(self.FIELD_TYPE[field], np.dtype): # dtype of scalar
                    rawvalue = np.array([ data[field.name] ])
                    if field in self.CONVERSION_FACTOR:
                        rawvalue /= self.CONVERSION_FACTOR[field]
                    msg += rawvalue.astype(self.FIELD_TYPE[field]).tobytes()
                    del rawvalue
                elif isinstance(self.FIELD_TYPE[field], tuple): # dtype and length of array
                    assert(len(data[field.name]) == self.FIELD_TYPE[field][1])
                    rawdata = np.array(data[field.name])
                    if field in self.CONVERSION_FACTOR:
                        rawdata /= self.CONVERSION_FACTOR[field]
                    msg += rawdata.astype(self.FIELD_TYPE[field]).tobytes()
                    del rawdata
                elif isinstance(self.FIELD_TYPE[field], int): # number of bytes
                    msg += np.zeros(self.FIELD_TYPE[field], dtype=np.uint8).tobytes()
        msg += np.uint8(TrackerMessageFields.ETX.value)
        cs_a, cs_b = self.checksum(msg)
        msg += cs_a
        msg += cs_b
        return msg


    def connect(self, host=None, user=None, password=None):
        """
        Connect to IMAP server.

        @param host server hostname
        @param user username
        @param password password

        @return imap imaplib object
        """
        self.imap = imaplib.IMAP4_SSL(host if host is not None else self.email_host) # connect to host using SSL
        self.imap.login(user if user is not None else self.email_user,
                        password if password is not None else self.email_password) # login to server
    
    
    def disconnect(self):
        """
        Disconnect from IMAP server.
        """
        self.imap.close()
        self.imap = None
        return


    def isConnected(self):
        """
        Check if connection ti IMAP server is established.
        """
        return self.imap is not None


    def extractEmailAttachment(self, num):
        """
        Extract SBD message attachment(s) from a given email via IMAP.
        """
        sbd_list = []
        typ, data = self.imap.fetch(num, '(RFC822)')
        raw_message = data[0][1]
        if sys.version_info[0] == 2:
            msg = email.message_from_string(raw_message)
        else:
            msg = email.message_from_bytes(raw_message)
        # Download attachments
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            filename = part.get_filename()
            if bool(filename):
                _, fileext = os.path.splitext(filename)
                if fileext in ['.sbd', '.bin']:
                    sbd_list.append(part.get_payload(decode=True))
                else:
                    logging.warning('receiveMessages: unrecognized file extension {} of attachment.'.format(fileext))
        return sbd_list
        
    
    def receiveMessages(self, from_address=None, unseen_only=True, first_only=False):
        """
        Query IMAP server for new mails from IRIDIUM gateway and extract new messages.
    
        @param from_address sender address to filter for
        @param unseen_only whether to only retrieve unseen messages (default: True)
        @param first_only whether to only retrieve the first message (default: False)
    
        @return sbd_list list of sbd attachments
        """
        if self.imap is None:
            raise ValueError('Cannot poll emails: not connected.')
        if from_address is None:
            from_address = self.email_from
        sbd_list = []
        self.imap.select('Inbox')
        criteria = ['FROM', from_address]
        if unseen_only:
            criteria.append('(UNSEEN)')
        retcode, messages = self.imap.search(None, *criteria)
        matches = messages[0].split()
        if first_only:
            if len(matches) > 0:
                return self.extractEmailAttachment(matches[0])
            else:
                return []
        else:
            for num in matches:
                sbd_list += self.extractEmailAttachment(num)
            return sbd_list


    def receiveMessage(self, from_address=None):
        """
        Receive next unread SBD message.
        """
        sbd_list = self.receiveMessages(from_address, unseen_only=True, first_only=True)
        if len(sbd_list) == 0:
            return None
        else:
            return sbd_list[0]


    def sendMessage(self, imei, data, user=None, password=None):
        """
        Send a mobile terminated (MT) message to a RockBLOCK device.
        """
        if user is None:
            user = self.rockblock_user
        if password is None:
            password = self.rockblock_password
        resp = requests.post(
                'https://core.rock7.com/rockblock/MT',
                data={'imei': imei, 'data': self.bin2asc(data),
                      'username': user, 'password': password})
        if not resp.ok:
            print('Error sending message: POST command failed: {}'.format(resp.text))
        parts = resp.text.split(',')
        if parts[0] == 'OK':
            try:
                logging.info('Message {} sent.'.format(parts[1]))
            except IndexError:
                logging.error('Unexpected server response format.')
            return True, 'OK'
        elif parts[0] == 'FAILED':
            error_message = ''
            try:
                logging.error('Sending message failed with error code {}: {}'.format(parts[1], parts[2]))
                error_message = parts[2]
            except IndexError:
                logging.error('Unexpected server response format.')
            return False, error_message
        else:
            error_message = 'Unexpected server response: {}'.format(resp.text)
            logging.error(error_message)
            return False, error_message


def fromSettings(settings):
    """
    Create a MessageSbd instance from settings.
    """
    return MessageSbd(
            email_host=settings['email']['host'],
            email_user=settings['email']['user'],
            email_password=settings['email']['password'],
            email_from=settings['email']['from'],
            rockblock_user=settings['rockblock']['user'],
            rockblock_password=settings['rockblock']['password'])


def retrieveMessages(config_file, all_messges=False, gpx_output_file=None, csv_output_file=None):
    """
    Retrieve messages and write out data.
    """
    from balloon_operator import trajectory_predictor
    config = configparser.ConfigParser()
    config.read(config_file)
    message_handler = MessageSbd(email_host=config['email']['host'],
                                 email_user=config['email']['user'],
                                 email_password=config['email']['password'])
    message_handler.connect()
    messages = message_handler.getDecodedMessages(from_address=config['email'].get('from', fallback='@rockblock.rock7.com'), unseen_only=not all_messges)
    message_handler.disconnect()
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    for msg in messages:
        print(msg)
        gpx_segment.points.append(message_handler.message2trackpoint(msg))
    if gpx_output_file:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.segments.append(gpx_segment)
        trajectory_predictor.writeGpx(gpx_track, gpx_output_file, name='Artemis Tracker')
    if csv_output_file and len(messages) > 0:
        # Write out last message in CSV format.
        line = '{},{:.7f},{:.7f},{:.1f}'.format(msg['DATETIME'].isoformat(), msg['LON'], msg['LAT'], msg['ALT'])
        if 'PRESS' in msg:
            line += ',{}'.format(msg['PRESS'])
        if 'TEMP' in msg:
            line += ',{:.1f}'.format(msg['TEMP'])
        if 'HUMID' in msg:
            line += ',{:.1f}'.format(msg['HUMID'])
        with open(csv_output_file, "w") as fd:
            fd.write(line+'\n')
    return


def encodeMessage(position=None, time=None, userfunc=None, output_file=None, send=None):
    """
    Encode binary SBD message corresponding to given data
    and write it to file or send it to mobile IRIDIUM device.
    """
    data = {}
    if position is not None:
        data.update({
            'LON': position[0],
            'LAT': position[1],
            'ALT': position[2]})
    if time:
        data.update({'DATETIME': time})
    if userfunc:
        data.update(userfunc)
    message_handler = MessageSbd()
    message = message_handler.encodeMessage(data)
    if output_file:
        with open(output_file, 'wb') as fd:
            fd.write(message)
    else:
        print(message_handler.bin2asc(message))
    if send:
        config = configparser.ConfigParser()
        config.read(send)
        status, error_message = message_handler.sendMessage(
                config['device']['imei'], message,
                config['rockblock']['user'], config['rockblock']['password'])
        if status:
            print('Message sent.')
        else:
            print('Error sending message: {}'.format(error_message))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser('SBD message translator and sender/receiver')
    parser.add_argument('-r', '--retrieve', required=False, default=None, help='Retrieve messages via IMAP as specified in configuration file')
    parser.add_argument('-a', '--all', required=False, action='store_true', default=False, help='Retrieve all messages, not only unread ones')
    parser.add_argument('-o', '--output', required=False, default=None, help='Output file')
    parser.add_argument('-c', '--csv', required=False, default=None, help='Write out coordinates in CSV format')
    parser.add_argument('-d', '--decode', required=False, default=None, help='Translate binary message given as hex string')
    parser.add_argument('-e', '--encode', required=False, action='store_true', default=False, help='Encode binary message')
    parser.add_argument('-p', '--position', required=False, default=None, help='Position lon,lat,alt')
    parser.add_argument('-t', '--time', required=False, nargs='?', default=None, const=datetime.datetime.utcnow(), help='UTC time in ISO format YYYY-mm-dd HH:MM:SS, or now if no argument given')
    parser.add_argument('-u', '--userfunc', required=False, default=None, help='User function (comma-separated list of functions to trigger)')
    parser.add_argument('-s', '--send', required=False, default=None, help='Send message to device as specified in configuration file')
    args = parser.parse_args()
    if args.encode:
        if args.position is not None:
            position = np.array(args.position.split(',')).astype(float)
        else:
            position = None
        if args.time is not None:
            if isinstance(args.time, datetime.datetime):
                time = args.time
            else:
                time = datetime.datetime.fromisoformat(args.time)
        else:
            time = None
        if args.userfunc is not None:
            userfunc = {}
            funcs = args.userfunc.split(',')
            for func in funcs:
                if ':' in func:
                    vals = func.split(':')
                    userfunc.update({'USERFUNC'+vals[0]: vals[1]})
                else:
                    userfunc.update({'USERFUNC'+func: True})
        else:
            userfunc = None
        encodeMessage(position=position, time=time, userfunc=userfunc, output_file=args.output, send=args.send)
    if args.decode is not None:
        message_handler = MessageSbd()
        if os.path.isfile(args.decode):
            with open(args.decode,'rb') as fd:
                msg_bin = fd.read()
                try:
                    msg_trans = message_handler.decodeMessage(msg_bin)
                except (ValueError, AssertionError, IndexError) as err:
                    print('Error translating message {}: {}'.format(args.decode, err))
                print(msg_trans)
        else:
            print(message_handler.decodeMessage(message_handler.asc2bin(args.decode)))
    if args.retrieve is not None:
        retrieveMessages(args.retrieve, all_messges=args.all,
                         gpx_output_file=args.output, csv_output_file=args.csv)
