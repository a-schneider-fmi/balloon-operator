#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for trajectory_predictor

Created on Sat Apr 24 18:33:56 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import datetime
from balloon_operator import trajectory_predictor, download_model_data


so_launch_lon = 26.6294
so_launch_lat = 67.3665


def test_readGfsData(verbose=False):
    """
    Unit test for readGfsData
    """
    model_path = '/tmp'
    launch_datetime = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    model_filename = download_model_data.getGfsData(so_launch_lon, so_launch_lat, launch_datetime, model_path)
    assert(model_filename is not None)
    model_data = trajectory_predictor.readGfsData(model_filename)


def test_equidistantAltitudeGrid(verbose=False):
    """
    Unit test for equidistantAltitudeGrid
    """
    datetime_vector, altitude_vector = trajectory_predictor.equidistantAltitudeGrid(
            datetime.datetime.fromisoformat('2021-01-01 00:00:00'), 0., 18000., 5, 10)
    assert(datetime_vector[0] == datetime.datetime.fromisoformat('2021-01-01 00:00:00'))
    assert(datetime_vector[-1] == datetime.datetime.fromisoformat('2021-01-01 01:00:00'))
    assert(altitude_vector[0] == 0)
    assert(altitude_vector[-1] == 18000)
    delta_t = datetime_vector[1:] - datetime_vector[:-1]
    assert(delta_t == datetime.timedelta(seconds=10)).all()
    delta_z = altitude_vector[1:] - altitude_vector[:-1]
    assert(delta_z == 5*10).all()
    datetime_vector, altitude_vector = trajectory_predictor.equidistantAltitudeGrid(
            datetime.datetime.fromisoformat('2021-01-01 00:00:00'), 18000., 0., -5, 10)
    assert(altitude_vector[0] == 18000)
    assert(altitude_vector[-1] == 0)


if __name__ == "__main__":
    test_readGfsData(verbose=True)
    test_equidistantAltitudeGrid(verbose=True)
