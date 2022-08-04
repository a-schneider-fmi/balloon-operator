#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for trajectory_predictor module.

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

import numpy as np
import datetime
from balloon_operator import trajectory_predictor, download_model_data, utils
import gpxpy
import gpxpy.gpx


# Test values
so_launch_lon = 26.6294
so_launch_lat = 67.3665
so_launch_alt = 179.
top_height = 30000
vertical_velocity = 5.
timestep = 10


def fakeGfsData(lon_range, lat_range, datetime_list, model_resolution=0.25, alt=so_launch_alt, u=0., v=0.):
    """
    Create fake GFS model data with constant data

    @param lon_range longitude range [lon_start, lon_end]
    @param lat_range latitude range [lat_start, lat_end]
    @param datetime_list list of datetimes
    @param model_resolution model resolution in degrees (default: 0.25)
    @param alt surface altitude in metres
    @param u value of constant u wind component in degrees per second (default: 0.)
    @param v value of constant v wind component in degrees per second (default: 0.)
    """
    if isinstance(datetime_list,datetime.datetime):
        datetime_list = [datetime_list]
    pressure_levels = np.array(
            [1., 2., 3., 5., 7., 10., 20., 30., 40., 50., 70., 100.,
             150., 200., 250., 300., 350., 400., 450., 500., 550., 600., 650.,
             700., 750., 800., 850., 900., 925., 950., 975., 1000.])*100.
    surface_pressure = 1000.*100.
    altitudes = utils.press2alt(pressure_levels, p0=surface_pressure) + alt
    lon_grid = np.arange(lon_range[0], lon_range[1]+model_resolution, model_resolution)
    lat_grid = np.arange(lat_range[0], lat_range[1]+model_resolution, model_resolution)
    data = {'datetime': datetime_list,
            'press': pressure_levels,
            'lon': lon_grid,
            'lat': lat_grid,
            'surface_pressure': surface_pressure * np.ones((len(datetime_list),len(lon_grid),len(lat_grid))),
            'surface_altitude': alt * np.ones((len(datetime_list),len(lon_grid),len(lat_grid))),
            'altitude': np.tile(
                    altitudes.reshape((1,len(altitudes),1,1)),
                    (len(datetime_list),1,len(lon_grid),len(lat_grid)) ),
            'u_wind_deg': u * np.ones((len(datetime_list),len(pressure_levels),len(lon_grid),len(lat_grid))),
            'v_wind_deg': v * np.ones((len(datetime_list),len(pressure_levels),len(lon_grid),len(lat_grid))),
            'proj': None, 'lev_type': 'press'}
    return data


def soFakeModelData(alt=so_launch_alt, u=0., v=0.):
    """
    Create fake model data for Sodankylä launch site
    """
    lon_range, lat_range = download_model_data.getLonLatArea(so_launch_lon, so_launch_lat)
    dt = utils.roundHours(datetime.datetime.utcnow(), 1)
    datetime_list = [dt + n*datetime.timedelta(hours=1) for n in range(3)]
    model_data = fakeGfsData(lon_range, lat_range, datetime_list, alt=alt, u=u, v=v)
    return model_data


def predictTrajectoryTest(lon0, lat0, alt0, alt1, u, v, vertical_velocity=vertical_velocity, verbose=False):
    """
    Perform one test of predictTrajectory with artificial data.
    """
    model_data = soFakeModelData(alt=alt0, u=u, v=v)
    dt, alt = trajectory_predictor.equidistantAltitudeGrid(
            model_data['datetime'][0], alt0, alt1, vertical_velocity, timestep)
    expected_lon = lon0 if u==0. else np.arange(lon0, lon0+u*timestep*len(alt)-u, u*timestep)
    expected_lat = lat0 if v==0. else np.arange(lat0, lat0+v*timestep*len(alt)-v, v*timestep)
    gpx_segment = trajectory_predictor.predictTrajectory(
            dt, alt, model_data, lon0, lat0)
    if verbose:
        print('Number of points: {} / {}'.format(len(alt), len(gpx_segment.points)))
    elev = np.array([point.elevation for point in gpx_segment.points])
    lon = np.array([point.longitude for point in gpx_segment.points])
    lat = np.array([point.latitude for point in gpx_segment.points])
    if len(alt) != len(gpx_segment.points):
        print(lon, lat, elev)
    eps_limit = 1e-10
    if isinstance(expected_lon,np.ndarray):
        assert (len(lon) == len(expected_lon)), 'Computed lon has different length than expected: {} != {}'.format(len(lon), len(expected_lon))
    rel_diff = (lon - expected_lon) / expected_lon
    assert (np.abs(rel_diff) < eps_limit).all(), 'lon does not match expected: relative differences {}'.format(rel_diff)
    if isinstance(expected_lat,np.ndarray):
        assert (len(lat) == len(expected_lat)), 'Computed lat has different length than expected: {} != {}'.format(len(lat), len(expected_lat))
    rel_diff = (lat - expected_lat) / expected_lat
    assert (np.abs(rel_diff) < eps_limit).all(), 'lat does not match expected: relative differences {}'.format(rel_diff)

def test_predictTrajectory(verbose=False):
    """
    Unit test for predictTrajectory
    """
    # Test with zero winds.
    predictTrajectoryTest(so_launch_lon, so_launch_lat, so_launch_alt, top_height, 0., 0., vertical_velocity, verbose=verbose)

    # Test with unit winds.
    predictTrajectoryTest(25., 63., 0., top_height, 0., 0.001, vertical_velocity=vertical_velocity, verbose=verbose)
    predictTrajectoryTest(20., 67., 0., top_height, 0.001, 0., vertical_velocity=vertical_velocity, verbose=verbose)


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
    test_predictTrajectory(verbose=True)
    test_checkBorderCrossing(verbose=True)
    test_main()
