#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit test for sbd_receiver.

Created on Fri May  7 10:28:30 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
import datetime
import gpxpy.gpx
from balloon_operator import sbd_receiver


def test_checksum(verbose=False):
    """
    Unit test for checksum
    """
    test_vectors = [b"abcde", b"abcdef", b"abcdefgh"]
    test_results = [(0xef, 0xc3), (0x55, 0x18), (0x24, 0xf8)]
    for ind in range(len(test_vectors)):
        cs_a, cs_b = sbd_receiver.checksum(test_vectors[ind])
        if verbose: print('{} -> {:x}, {:x}'.format(test_vectors[ind], cs_a, cs_b))
        assert(cs_a == test_results[ind][0] and cs_b == test_results[ind][1])


def test_parseSbd(verbose=False):
    """
    Unit test for parseSbd
    """
    test_message = b'\x02\ti\x01\n\xcf\x03\x0b\x1d\x05\x14\xe5\x07\x05\x07\n\x17\x19\x15"T\'(\x16\x9eG\xdf\x0f\x17\x12\xe1\x02\x00\x03\x96n'
    message_translation = {
            'BATTV': 3.61, 'PRESS': 975, 'TEMP': 13.09, 
            'DATETIME': datetime.datetime(2021, 5, 7, 10, 23, 25),
            'LAT': 67.3666082, 'LON': 26.6291102, 'ALT': 188.69}
    data = sbd_receiver.parseSbd(test_message)
    if verbose: print(data)
    assert(data == message_translation)


def test_encodeSdb(verbose=False):
    """
    Unit test for encodeSbd
    """
    test_data = {
            'BATTV': 3.61, 'PRESS': 975, 'TEMP': 13.09, 
            'DATETIME': datetime.datetime(2021, 5, 7, 10, 23, 25),
            'LAT': 67.3666082, 'LON': 26.6291102, 'ALT': 188.69}
    message = sbd_receiver.encodeSdb(test_data)
    if verbose: print(message)
    assert(sbd_receiver.parseSbd(message) == test_data)


def test_message2trackpoint(verbose=False):
    """
    Unit test for message2trackpoint
    """
    message = {
            'DATETIME': datetime.datetime(2021, 5, 7, 10, 23, 25),
            'LAT': 67.3666082, 'LON': 26.6291102, 'ALT': 188.69}
    gpx_point = sbd_receiver.message2trackpoint(message)
    if verbose: print(gpx_point)
    assert(gpx_point.latitude == 67.3666082)
    assert(gpx_point.longitude == 26.6291102)
    assert(gpx_point.elevation == 188.69)
    assert(gpx_point.time == datetime.datetime(2021, 5, 7, 10, 23, 25))


if __name__ == "__main__":
    test_checksum(verbose=True)
    test_parseSbd(verbose=True)
    test_encodeSdb(verbose=True)
    test_message2trackpoint(verbose=True)
