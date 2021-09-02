#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a binary sbd file in format of SparkFun Artemis Global Tracker.

Created on Mon May 24 13:52:19 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
import datetime
import requests
import configparser
import argparse
import logging
from balloon_operator import sbd_receiver


def sendMessage(imei, data, username, password):
    """
    Send a mobile terminated (MT) message to a RockBLOCK device.
    """
    resp = requests.post(
            'https://core.rock7.com/rockblock/MT',
            data={'imei': imei, 'data': sbd_receiver.bin2asc(data),
                  'username': username, 'password': password})
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


def main(position=None, time=None, userfunc=None, output_file=None, send=None):
    """
    Main: Encode binary SBD message corresponding to given data
    and write it to file or send it to mobile IRIDIUM device.
    """
    data = {}
    if position:
        data.update({
            'LON': position[0],
            'LAT': position[1],
            'ALT': position[2]})
    if time:
        data.update({'DATETIME': time})
    if userfunc:
        data.update(userfunc)
    message = sbd_receiver.encodeSdb(data)
    if output_file:
        with open(output_file, 'wb') as fd:
            fd.write(message)
    else:
        print(sbd_receiver.bin2asc(message))
    if send:
        config = configparser.ConfigParser()
        config.read(send)
        status, error_message = sendMessage(
                config['device']['imei'], message,
                config['rockblock']['user'], config['rockblock']['password'])
        if status:
            print('Message sent.')
        else:
            print('Error sending message: {}'.format(error_message))
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--position', required=False, default=None, help='Position lon,lat,alt')
    parser.add_argument('-t', '--time', required=False, nargs='?', default=None, const=datetime.datetime.utcnow, help='UTC time in ISO format YYYY-mm-dd HH:MM:SS, or now if no argument given')
    parser.add_argument('-u', '--userfunc', required=False, default=None, help='User function (comma-separated list of functions to trigger)')
    parser.add_argument('-o', '--output', required=False, default=None, help='Output file')
    parser.add_argument('-s', '--send', required=False, default=None, help='Send message to device as specified in configuration file')
    args = parser.parse_args()
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
                
    main(position=position, time=time, userfunc=userfunc, output_file=args.output, send=args.send)
