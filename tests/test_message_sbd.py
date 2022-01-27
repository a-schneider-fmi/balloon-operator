#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit test for message_sbd.

Created on Fri May  7 10:28:30 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
import datetime
import gpxpy.gpx
from balloon_operator import message_sbd


def test_checksum(verbose=False):
    """
    Unit test for checksum
    """
    test_vectors = [b"abcde", b"abcdef", b"abcdefgh"]
    test_results = [(0xef, 0xc3), (0x55, 0x18), (0x24, 0xf8)]
    for ind in range(len(test_vectors)):
        cs_a, cs_b = message_sbd.MessageSbd.checksum(test_vectors[ind])
        if verbose: print('{} -> {:x}, {:x}'.format(test_vectors[ind], cs_a, cs_b))
        assert(cs_a == test_results[ind][0] and cs_b == test_results[ind][1])


def test_decodeMessage(verbose=False):
    """
    Unit test for parseSbd
    """
    test_message = b'\x02\ti\x01\n\xcf\x03\x0b\x1d\x05\x14\xe5\x07\x05\x07\n\x17\x19\x15"T\'(\x16\x9eG\xdf\x0f\x17\x12\xe1\x02\x00\x03\x96n'
    message_translation = {
            'BATTV': 3.61, 'PRESS': 975, 'TEMP': 13.09, 
            'DATETIME': datetime.datetime(2021, 5, 7, 10, 23, 25),
            'LAT': 67.3666082, 'LON': 26.6291102, 'ALT': 188.69}
    message_handler = message_sbd.MessageSbd()
    data = message_handler.decodeMessage(test_message)
    if verbose: print(data)
    assert(data == message_translation)


def test_encodeMessage(verbose=False):
    """
    Unit test for encodeSbd
    """
    test_data = {
            'BATTV': 3.61, 'PRESS': 975, 'TEMP': 13.09, 
            'DATETIME': datetime.datetime(2021, 5, 7, 10, 23, 25),
            'LAT': 67.3666082, 'LON': 26.6291102, 'ALT': 188.69}
    message_handler = message_sbd.MessageSbd()
    message = message_handler.encodeMessage(test_data)
    if verbose: print(message)
    assert(message_handler.decodeMessage(message) == test_data)


def test_asc2bin(verbose=False):
    """
    Unit test for asc2bin
    """
    msg_asc = '020969010ACF030B1D0514E50705070A17191522542728169E47DF0F1712E1020003966E'
    msg_bin = b'\x02\ti\x01\n\xcf\x03\x0b\x1d\x05\x14\xe5\x07\x05\x07\n\x17\x19\x15"T\'(\x16\x9eG\xdf\x0f\x17\x12\xe1\x02\x00\x03\x96n'
    assert(message_sbd.MessageSbd.asc2bin(msg_asc) == msg_bin)
    assert(message_sbd.MessageSbd.asc2bin(message_sbd.MessageSbd.bin2asc(msg_bin)) == msg_bin)


if __name__ == "__main__":
    test_checksum(verbose=True)
    test_decodeMessage(verbose=True)
    test_encodeMessage(verbose=True)
    test_asc2bin(verbose=True)
