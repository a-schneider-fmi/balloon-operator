#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for download_model_data module.

Copyright (C) 2021 Andreas Schneider <andreas.schneider@fmi.fi>

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

from balloon_operator import download_model_data
import datetime
import os.path
import numpy as np

so_launch_lon = 26.6294
so_launch_lat = 67.3665

def test_modelFilename(verbose=False):
    """
    Unit test for modelFilename
    """
    filename = download_model_data.modelFilename(
            'gfs', [0.,24.], [46.75, 61.5],
            datetime.datetime.combine(datetime.date.today(), datetime.time(0,0,0)), 
            np.random.randint(120),
            model_resolution=0.25)
    if verbose:
        print(filename)
    name, ext = os.path.splitext(filename)
    assert(ext == '.grb2')

def test_getModelArea(verbose=False):
    """
    Unit test for getModelArea.
    """
    lon_range, lat_range = download_model_data.getModelArea(so_launch_lon, so_launch_lat)
    if verbose:
        print('{} {} {} {}'.format(lon_range[0], lat_range[0], lon_range[1], lat_range[1]))

def test_getGfsData(verbose=False):
    """
    Unit test for getGfsData
    """
    launch_datetime = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    filename = download_model_data.getGfsData(
            so_launch_lon, so_launch_lat, launch_datetime, '/tmp')
    assert(filename is not None)

if __name__ == "__main__":
    test_modelFilename(verbose=True)
    test_getModelArea(verbose=True)
    test_getGfsData(verbose=True)
