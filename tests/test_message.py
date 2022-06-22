#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for message module.

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
