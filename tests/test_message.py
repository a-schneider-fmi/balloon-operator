#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 25 13:14:33 2022
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import datetime
from balloon_operator import message


def test_message2point(verbose=False):
    """
    Unit test for message2trackpoint
    """
    msg = {
            'DATETIME': datetime.datetime(2021, 5, 7, 10, 23, 25),
            'LAT': 67.3666082, 'LON': 26.6291102, 'ALT': 188.69}
    trkpt = message.Message.message2trackpoint(msg)
    wpt = message.Message.message2waypoint(msg)
    for gpx_point in [trkpt, wpt]:
        if verbose: print(gpx_point)
        assert(gpx_point.latitude == 67.3666082)
        assert(gpx_point.longitude == 26.6291102)
        assert(gpx_point.elevation == 188.69)
        assert(gpx_point.time == datetime.datetime(2021, 5, 7, 10, 23, 25))


if __name__ == "__main__":
    test_message2point(verbose=True)
