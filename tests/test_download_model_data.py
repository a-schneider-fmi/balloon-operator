#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 18 18:05:28 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
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
