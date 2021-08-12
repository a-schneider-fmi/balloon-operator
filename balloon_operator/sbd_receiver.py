#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Receive and parse IRIDIUM SBD messages from RockBLOCK devices.

Created on Fri May  7 08:06:27 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
from enum import Enum
import datetime
import struct
import gpxpy
import gpxpy.gpx
import configparser
import imaplib
import email
import os.path
import sys
import argparse
import logging
from balloon_operator import trajectory_predictor


class TrackerMessageFields(Enum):
    """
    Define the message field IDs used in the binary format MO and MT messages.
    Taken over from Tracker_Message_Fields.h
    https://github.com/sparkfunX/Artemis_Global_Tracker/blob/master/Software/examples/Example16_GlobalTracker/Tracker_Message_Fields.h
    """
    STX       = 0x02
    ETX       = 0x03
    SWVER     = 0x04
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

"""
Define the type of the binary data fields.
Either a dtype or a length in bytes for more complicated cases.
Entries according to Tracker_Message_Fields.h
"""
FIELD_TYPE = {
        TrackerMessageFields.STX: 0,
        TrackerMessageFields.ETX: 0,
        TrackerMessageFields.SWVER: np.dtype('uint8'),
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
        TrackerMessageFields.USERVAL4: np.dtype('uint16'),
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
Conversion factors for data fields according to documentation.
"""
CONVERSION_FACTOR = {
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


def checksum(data):
    """
    Compute checksum bytes are as defined in the 8-Bit Fletcher Algorithm,
    used by the TCP standard (RFC 1145).

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


def parseSbd(message):
    """
    Parse binary SBD message from Sparkfun Artemis Global Tracker.

    File format documented at https://github.com/sparkfunX/Artemis_Global_Tracker under
    * Documentation/Message_Format/README.md
    * Software/examples/Example16_GlobalTracker/Tracker_Message_Fields.h

    @param message message as byte array

    @return data translated message as dictionary
    """
    data = {}
    if message[0] == TrackerMessageFields.STX.value:
        ind = 0
    else: # assuming 
        ind = 5
    assert(message[ind] == TrackerMessageFields.STX.value)
    ind += 1
    while (message[ind] != TrackerMessageFields.ETX.value):
        field = TrackerMessageFields(message[ind])
        ind += 1
        if isinstance(FIELD_TYPE[field], int): # length in bytes
            field_len = FIELD_TYPE[field]
            if field == TrackerMessageFields.DATETIME:
                values = struct.unpack('HBBBBB', message[ind:ind+field_len])
                logging.debug('  DATETIME: {}'.format(values))
                data[field.name] = datetime.datetime(*values)
            elif field_len > 0:
                data[field.name] = message[ind:ind+field_len]
            else:
                data[field.name] = None
        elif isinstance(FIELD_TYPE[field], np.dtype): # dtype of scalar
            field_len = FIELD_TYPE[field].itemsize
            data[field.name] = np.frombuffer(message[ind:ind+field_len], dtype=FIELD_TYPE[field])[0]
        elif isinstance(FIELD_TYPE[field], tuple): # dtype and length of array
            field_len = FIELD_TYPE[field][0].itemsize * FIELD_TYPE[field][1]
            data[field.name] = np.frombuffer(message[ind:ind+field_len], dtype=FIELD_TYPE[field][0])
        else:
            raise ValueError('Unknown entry in FIELD_TYPE list: {}'.format(FIELD_TYPE[field]))
        if field in CONVERSION_FACTOR:
            data[field.name] = float(data[field.name]) * CONVERSION_FACTOR[field]
        ind += field_len
    ind += 1 # ETX
    cs_a, cs_b = checksum(message[:ind])
    assert (message[ind] == cs_a), 'Checksum mismatch'
    assert (message[ind+1] == cs_b), 'Checksum mismatch'
    return data


def encodeSdb(data):
    """
    Create a binary SBD message in Sparkfun Artemis Global Tracker format.

    @param data dictionary with data to send, with keys named according to TrackerMessageFields names

    @return message encoded binary SBD message
    """
    message = b''
    message += np.uint8(TrackerMessageFields.STX.value)
    for field in TrackerMessageFields:
        if field.name in data:
            message += np.uint8(field.value)
            if field == TrackerMessageFields.DATETIME:
                message += struct.pack(
                        'HBBBBB',
                        data[field.name].year, data[field.name].month,
                        data[field.name].day, data[field.name].hour,
                        data[field.name].minute, data[field.name].second)
            elif isinstance(FIELD_TYPE[field], np.dtype): # dtype of scalar
                rawvalue = np.array([ data[field.name] ])
                if field in CONVERSION_FACTOR:
                    rawvalue /= CONVERSION_FACTOR[field]
                message += rawvalue.astype(FIELD_TYPE[field]).tobytes()
                del rawvalue
            elif isinstance(FIELD_TYPE[field], tuple): # dtype and length of array
                assert(len(data[field.name]) == FIELD_TYPE[field][1])
                rawdata = np.array(data[field.name])
                if field in CONVERSION_FACTOR:
                    rawdata /= CONVERSION_FACTOR[field]
                message += rawdata.astype(FIELD_TYPE[field]).tobytes()
                del rawdata
            elif isinstance(FIELD_TYPE[field], int): # number of bytes
                message += np.zeros(FIELD_TYPE[field], dtype=np.uint8).tobytes()
    message += np.uint8(TrackerMessageFields.ETX.value)
    cs_a, cs_b = checksum(message)
    message += cs_a
    message += cs_b
    return message


def asc2bin(msg_asc):
    """
    Convert ASCII representation of binary message to real binary message.
    """
    msg = b''
    for ind in np.arange(0,len(msg_asc),2):
        msg += np.uint8(int(msg_asc[ind:ind+2], 16))
    return msg


def bin2asc(msg_bin):
    """
    Encode binary message to ASCII representation.
    """
    msg_asc = ''
    for ind in range(len(msg_bin)):
        msg_asc += '{:02x}'.format(msg_bin[ind])
    return msg_asc


def message2trackpoint(msg):
    """
    Creates a GPX trackpoint from a translated IRIDIUM message.

    @param msg translated SBD message

    @return pkt GPX trackpoint corresponding to message data
    """
    return gpxpy.gpx.GPXTrackPoint(
                msg['LAT'], msg['LON'], elevation=msg['ALT'], time=msg['DATETIME'],
                comment='{} hPa'.format(msg['PRESS']) if 'PRESS' in msg else None)


def message2waypoint(msg, name='Current'):
    """
    Creates a GPX waypoint from a translated IRIDIUM message.

    @param msg translated SBD message
    @param name name of the waypoint (default: 'Current')

    @return pkt GPX waypoint corresponding to message data
    """
    status_text = ''
    if 'PRESS' in msg:
        status_text += 'Pressure: {} hPa\n'.format(msg['PRESS'])
    if 'TEMP' in msg:
        status_text += 'Temperature: {:.1f} °C\n'.format(msg['TEMP'])
    if 'BATTV' in msg:
        status_text += 'Battery: {:.2f} V\n'.format(msg['BATTV'])
    pkt = gpxpy.gpx.GPXWaypoint(
        msg['LAT'], msg['LON'], elevation=msg['ALT'], time=msg['DATETIME'],
        name=name, description=status_text)
    return pkt


def connectImap(host, user, password):
    """
    Connect to IMAP server.

    @param host server hostname
    @param user username
    @param password password

    @return imap imaplib object
    """
    imap = imaplib.IMAP4_SSL(host) # connect to host using SSL
    imap.login(user, password) # login to server
    return imap


def disconnectImap(imap):
    """
    Disconnect from IMAP server.

    @param imap imaplib object
    """
    imap.close()
    return
    

def queryMail(imap, from_address='@rockblock.rock7.com', unseen_only=True):
    """
    Query IMAP server for new mails from IRIDIUM gateway and extract new messages.

    @param imap imaplib object with open connection
    @param from_address sender address to filter for
    @param unseen_only whether to only retrieve unseen messages (default: True)

    @return sbd_list list of sbd attachments
    """
    sbd_list = []
    imap.select('Inbox')
    criteria = ['FROM', from_address]
    if unseen_only:
        criteria.append('(UNSEEN)')
    retcode, messages = imap.search(None, *criteria)
    for num in messages[0].split():
        typ, data = imap.fetch(num, '(RFC822)')
        raw_message = data[0][1]
        if sys.version_info[0] == 2:
            message = email.message_from_string(raw_message)
        else:
            message = email.message_from_bytes(raw_message)
        # Download attachments
        for part in message.walk():
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
                    logging.warning('queryMail: unrecognized file extension {} of attachment.'.format(fileext))
    return sbd_list


def getMessages(imap, from_address='@rockblock.rock7.com', all_messges=False):
    """
    Get IRIDIUM SBD messages from IMAP.

    @param imap imaplib object with open connection
    @param from_address sender address to filter for
    @param unseen_only whether to only retrieve unseen messages (default: True)

    @return messages translated messages
    """
    messages = []
    sbd_list = queryMail(imap, from_address=from_address, unseen_only=not all_messges)
    for sbd in sbd_list:
        try:
            messages.append(parseSbd(sbd))
        except (ValueError, AssertionError) as err:
            logging.error('Error parsing message: {}'.format(err))
            pass
    return messages


def main(config_file, output_file=None, all_messges=False):
    """
    Main function.
    """
    config = configparser.ConfigParser()
    config.read(config_file)
    imap = connectImap(config['email']['host'], config['email']['user'], config['email']['password'])
    messages = getMessages(imap, from_address=config['email'].get('from', fallback='@rockblock.rock7.com'), all_messges=all_messges)
    disconnectImap(imap)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    for msg in messages:
        print(msg)
        gpx_segment.points.append(message2trackpoint(msg))
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.segments.append(gpx_segment)
    if output_file:
        trajectory_predictor.writeGpx(gpx_track, output_file, name='Artemis Tracker')
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--ini', required=False, default='comm.ini', help='Configuration ini file name')
    parser.add_argument('-a', '--all', required=False, action='store_true', default=False, help='Retrieve all messages, not only unread ones')
    parser.add_argument('-o', '--output', required=False, default=None, help='Output file')
    parser.add_argument('-m', '--message', required=False, default=None, help='Translate binary message given as hex string')
    args = parser.parse_args()
    if args.message is not None:
        if os.path.isfile(args.message):
            with open(args.message,'rb') as fd:
                msg_bin = fd.read()
                try:
                    msg_trans = parseSbd(msg_bin)
                except (ValueError, AssertionError, IndexError) as err:
                    print('Error translating message {}: {}'.format(args.message, err))
                print(msg_trans)
        else:
            print(parseSbd(asc2bin(args.message)))
    else:
        main(args.ini, args.output, all_messges=args.all)
