#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for trajectory_predictor

Created on Sat Apr 24 18:33:56 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import datetime
from balloon_operator import trajectory_predictor, download_model_data
import gpxpy
import gpxpy.gpx


so_launch_lon = 26.6294
so_launch_lat = 67.3665


def test_readGfsDataFiles(verbose=False):
    """
    Unit test for readGfsDataFile
    """
    model_path = '/tmp'
    launch_datetime = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    model_filenames = download_model_data.getGfsData(so_launch_lon, so_launch_lat, launch_datetime, model_path)
    assert(model_filenames is not None)
    model_data = trajectory_predictor.readGfsDataFiles(model_filenames)


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


def test_checkBorderCrossing(verbose=False):
    """
    Unit test for checkBorderCrossing
    """
    segment = gpxpy.gpx.GPXTrackSegment()
    track = gpxpy.gpx.GPXTrack()
    track.segments.append(segment)
    segment.points.append(gpxpy.gpx.GPXTrackPoint(so_launch_lat, so_launch_lon))
    segment.points.append(gpxpy.gpx.GPXTrackPoint(67, 27)) # domestic point
    is_abroad, foreign_countries = trajectory_predictor.checkBorderCrossing(track)
    if verbose:
        print(is_abroad, foreign_countries)
    assert(len(is_abroad) == 2 and (~is_abroad).all())
    segment.points.append(gpxpy.gpx.GPXTrackPoint(67, 22)) # foreign point
    is_abroad, foreign_countries = trajectory_predictor.checkBorderCrossing(track)
    if verbose:
        print(is_abroad, foreign_countries)
    assert(len(is_abroad) == 3 and is_abroad[2] == True)
    assert(len(foreign_countries) == 1)
    assert('SE' in foreign_countries)


def test_main():
    """
    Test of main function
    """
    dt = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    trajectory_predictor.main(dt)
    trajectory_predictor.main(dt, descent_only=True)
    trajectory_predictor.main(dt, config_file='aircore.ini')
    trajectory_predictor.main(dt, config_file='aircore.ini', descent_only=True)
    trajectory_predictor.main(dt, config_file='aircore.ini', hourly=6)


if __name__ == "__main__":
    test_readGfsDataFiles(verbose=True)
    test_equidistantAltitudeGrid(verbose=True)
    test_checkBorderCrossing(verbose=True)
    test_main()
