#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module to predict trajectories of balloon flights.

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

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import curve_fit
import pygrib
import datetime
import time
import gpxpy
import gpxpy.gpx
import srtm
import geog
import configparser
import os.path
import argparse
import logging
import tempfile
from copy import deepcopy
import traceback
from balloon_operator import filling, parachute, download_model_data, constants, message, message_sbd, message_file, comm, utils


def m2deg(lon, lat, u, v):
    """
    Convert winds u, v from m/s to deg/s.

    @param lon longitude grid
    @param lat latitude grid
    @param u u winds in m/s
    @param v v winds in m/s

    @return u_deg u winds in deg/s
    @return v_deg v winds in deg/s
    """
    u_deg = u*360./np.tile(2.*np.pi*constants.r_earth*np.cos(np.radians(lat)), (len(lon),1))
    v_deg = v*360./(2.*np.pi*constants.r_earth)
    return u_deg, v_deg


def readGfsDataFile(filename):
    """
    Read in GFS data file

    @param filename name of GFS GRIB data file

    @return model_data a dictionary with the model data with the following keys:
        'datetime', 'press', 'lon', 'lat', 'surface_pressure', 'surface_altitude',
        'altitude', 'u_wind_deg', 'v_wind_deg'
    """
    grbidx = pygrib.open(filename)
    # Get levels in GRIB file. Assume all variables have same order of levels.
    levels = []
    lat = None
    lon = None
    for grb in grbidx:
        if grb.name == 'U component of wind':
            levels.append(grb.level)
            lat, lon = grb.latlons()
            lat = lat[:,0]
            lon = lon[0,:]
            dt = grb.validDate
    if lat is None or lon is None:
        logging.error('Error: No valid U entries in grib file {}!'.format(filename))
        return None
    # Read in data.
    u_wind = np.zeros((len(levels), len(lon), len(lat)))
    v_wind = np.zeros((len(levels), len(lon), len(lat)))
    altitude = np.zeros((len(levels), len(lon), len(lat)))
    surface_pressure = None
    surface_altitude = None
    grbidx.seek(0)
    ind_level_u = 0
    ind_level_v = 0
    ind_level_alt = 0
    for grb in grbidx:
        if grb.name == 'U component of wind':
            assert(grb.level == levels[ind_level_u])
            u_wind[ind_level_u, :, :] = grb.values.transpose()
            ind_level_u += 1
        elif grb.name == 'V component of wind':
            assert(grb.level == levels[ind_level_v])
            v_wind[ind_level_v, :, :] = grb.values.transpose()
            ind_level_v += 1
        elif grb.name == 'Geopotential Height':
            assert(grb.level == levels[ind_level_alt])
            altitude[ind_level_alt, :, :] = grb.values.transpose()
            ind_level_alt += 1
        elif grb.name == 'Surface pressure':
            surface_pressure = grb.values.transpose()
        elif grb.name == 'Orography':
            surface_altitude = grb.values.transpose()
        else:
            logging.warning('Unused variable: {}'.format(grb.name))
    grbidx.close()
    # Convert winds from m/s to deg/s
    for ind_level in range(len(levels)):
        u_wind[ind_level, :, :], v_wind[ind_level, :, :] = m2deg(lon, lat, u_wind[ind_level, :, :], v_wind[ind_level, :, :])
    return {'datetime': dt, 'press': np.array(levels)*100., 'lon': lon, 'lat': lat, # convert levels from hPa to Pa
            'surface_pressure': surface_pressure, 'surface_altitude': surface_altitude, 
            'altitude': altitude, 'u_wind_deg': u_wind, 'v_wind_deg': v_wind}


def readGfsDataFiles(filelist):
    """
    Read in a collection of GFS data files.

    @param filelist list of filenames to read

    @return data a dictionary with the read model data with the following keys:
        'datetime', 'press', 'lon', 'lat', 'surface_pressure', 'surface_altitude',
        'altitude', 'u_wind_deg', 'v_wind_deg'
        Variables (but not lon, lat, press) have one dimension more than from readGfsDataFile.
    """
    data = None
    idx_keep = np.ones(len(filelist), dtype=bool)
    for ind_file in range(len(filelist)):
        if filelist[ind_file] is None:
            continue
        this_data = readGfsDataFile(filelist[ind_file])
        if this_data is None:
            idx_keep[ind_file] = False
            continue
        if data is None:
            data = {'datetime': np.array([None]*len(filelist)),
                    'press': this_data['press'],
                    'lon': this_data['lon'],
                    'lat': this_data['lat'],
                    'surface_pressure': np.zeros((len(filelist),len(this_data['lon']),len(this_data['lat']))),
                    'surface_altitude': np.zeros((len(filelist),len(this_data['lon']),len(this_data['lat']))),
                    'altitude': np.zeros((len(filelist),len(this_data['press']),len(this_data['lon']),len(this_data['lat']))),
                    'u_wind_deg': np.zeros((len(filelist),len(this_data['press']),len(this_data['lon']),len(this_data['lat']))),
                    'v_wind_deg': np.zeros((len(filelist),len(this_data['press']),len(this_data['lon']),len(this_data['lat'])))}
        data['datetime'][ind_file] = this_data['datetime']
        assert (data['press'].shape == this_data['press'].shape and (data['press'] == this_data['press']).all())
        assert (data['lon'].shape == this_data['lon'].shape and (data['lon'] == this_data['lon']).all())
        assert (data['lat'].shape == this_data['lat'].shape and (data['lat'] == this_data['lat']).all())
        data['surface_pressure'][ind_file,:,:] = this_data['surface_pressure']
        data['surface_altitude'][ind_file,:,:] = this_data['surface_altitude']
        data['altitude'][ind_file,:,:,:] = this_data['altitude']
        data['u_wind_deg'][ind_file,:,:,:] = this_data['u_wind_deg']
        data['v_wind_deg'][ind_file,:,:,:] = this_data['v_wind_deg']
        del this_data
    if not idx_keep.all():
        logging.warning('{} GRIB files damaged! Not using them.'.format(np.count_nonzero(idx_keep)))
        for qty in ['surface_pressure', 'surface_altitude']:
            data[qty] = data[qty][idx_keep,:,:]
        for qty in ['altitude', 'u_wind_deg', 'v_wind_deg']:
            data[qty] = data[qty][idx_keep,:,:,:]
    return data


def equidistantAltitudeGrid(start_datetime, start_altitude, end_altitude, ascent_velocity, timestep):
    """
    Compute time and altitude grid for constant vertical velocity.

    @param start_altitude start altitude
    @param end_altitude end altitude
    @param ascent_velocity ascent velocity, use negative value for descent
    @param timestep time step

    @return datetime_vector datetime vector of the grid
    @return altitude_vector altitude vector of the grid
    """
    duration = (end_altitude - start_altitude) / ascent_velocity # in s
    top_datetime = start_datetime + datetime.timedelta(seconds=duration)
    datetime_vector = start_datetime + np.array([datetime.timedelta(seconds=seconds) for seconds in np.arange(0, duration, timestep)])
    altitude_vector = np.arange(start_altitude, end_altitude, ascent_velocity*timestep)
    assert(len(datetime_vector) == len(altitude_vector))
    datetime_vector = np.append(datetime_vector, top_datetime)
    altitude_vector = np.append(altitude_vector, end_altitude)
    return datetime_vector, altitude_vector


def predictTrajectory(dt, altitude, model_data, lon_start, lat_start):
    """
    Predict balloon trajectory for given altitude array using given model wind data.

    @param dt datetime vector
    @param altitude altitude vector
    @param model_data model data
    @param lon_start start longitude in degrees
    @param lat_start start latitude in degrees

    @return gpx_segment gpxpy.gpx.GPXTrackSegment object with trajectory
    """
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    # Compute pressure for given altitude array by interpolating the model near
    # the launch position with an exponential fit.
    i_start = np.argmin(np.abs(model_data['lon']-lon_start))
    j_start = np.argmin(np.abs(model_data['lat']-lat_start))
    t_start = 0
    expfun = lambda x,a,b: a*np.exp(b*x)
    popt, pcov = curve_fit(expfun,  model_data['altitude'][t_start, :, i_start, j_start],  model_data['press'],  p0=(model_data['surface_pressure'][t_start, i_start, j_start], -1./8300.))
    pressure = expfun(altitude, popt[0], popt[1])
    max_model_press = np.max(model_data['press'])
    min_model_press = np.min(model_data['press'])
    pressure[pressure > max_model_press] = max_model_press # Cap pressures larger than maximum of model grid to avoid extrapolation.
    pressure[pressure < min_model_press] = min_model_press # Cap pressures lower than maximum of model grid to avoid extrapolation.
    # Displace balloon by model winds.
    lon = lon_start
    lat = lat_start
    time_grid = np.array([(this_dt-model_data['datetime'][0]).total_seconds() for this_dt in model_data['datetime']])
    interp_u = RegularGridInterpolator((time_grid,model_data['press'],model_data['lon'],model_data['lat']), model_data['u_wind_deg'])
    interp_v = RegularGridInterpolator((time_grid,model_data['press'],model_data['lon'],model_data['lat']), model_data['v_wind_deg'])
    has_landed = False
    for ind in range(len(dt)):
        if ind > 0:
            delta_t = (dt[ind] - dt[ind-1]).total_seconds()
            grid_time = (dt[ind]-model_data['datetime'][0]).total_seconds()
            if grid_time > time_grid[-1]:
                grid_time = time_grid[-1] # Cap time outside grid
                logging.warning('Capping time outside grid: {} > {}'.format(dt[ind], model_data['datetime'][-1]))
            if grid_time < time_grid[0]:
                grid_time = time_grid[0] # Cap time outside grid
                logging.warning('Capping time outside grid: {} < {}'.format(dt[ind], model_data['datetime'][0]))
            try:
                u = interp_u([grid_time, pressure[ind], lon, lat])[0]
                v = interp_v([grid_time, pressure[ind], lon, lat])[0]
            except ValueError as err:
                logging.error('Error interpolating winds: {}'.format(err))
                continue
            lon += delta_t * u
            lat += delta_t * v
            surface_elevation = srtm.get_elevation(lat, lon)
            if surface_elevation is not None and altitude[ind] <= surface_elevation:
                # Compute after which fraction of the last time step the ground
                # has been hit, and go back accordingly.
                # This approach assumes no steep slopes.
                below_ground = surface_elevation - altitude[ind]
                timestep_fraction = below_ground / (altitude[ind] - altitude[ind-1])
                lon -= timestep_fraction * delta_t * u
                lat -= timestep_fraction * delta_t * v
                dt -= datetime.timedelta(seconds=timestep_fraction*delta_t)
                has_landed = True
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                lat, lon, elevation=altitude[ind], time=dt[ind], 
                comment='{:.2f} hPa'.format(pressure[ind]/100.)))
        if has_landed:
            break
    return gpx_segment


def predictAscent(launch_datetime, launch_lon, launch_lat, launch_altitude,
                  top_height, ascent_velocity, model_data, timestep):
    """
    Predict trajectory for balloon ascent.

    @param launch_datetime datetime of launch
    @param launch_lon longitude of launch in degrees
    @param launch_lat latitude of launch in degrees
    @param launch_altitude altitude of launch in m
    @param top_height ceiling of balloon in m
    @param ascent_velocity balloon ascent velocity in m/s
    @param model_data model data
    @param timestep time step in s

    @return segment_ascent trajectory as gpxpy.gpx.GPXTrackSegment object
    @return top_lon ceiling longitude in degrees
    @return top_lat ceiling latitude in degrees
    @return top_datetime ceiling datetime
    """
    datetime_ascent, alt_ascent = equidistantAltitudeGrid(launch_datetime, launch_altitude, top_height, ascent_velocity, timestep)
    segment_ascent = predictTrajectory(datetime_ascent, alt_ascent, model_data, launch_lon, launch_lat)
    top_lon = segment_ascent.points[-1].longitude
    top_lat = segment_ascent.points[-1].latitude
    top_datetime = datetime_ascent[-1]
    top_datetime = utils.roundSeconds(top_datetime, 1) # round up to next full second
    return segment_ascent, top_lon, top_lat, top_datetime


def predictDescent(top_datetime, top_lon, top_lat, top_height, descent_velocity, 
                   parachute_parameters, payload_weight, payload_area, model_data, timestep,
                   initial_velocity=0.):
    """
    Predict trajectory for balloon descent.

    @param top_datetime datetime at ceiling
    @param top_lon longitude at ceiling in degrees
    @param top_lat latitude at ceiling in degrees
    @param top_height altitude at ceiling in m
    @param descent_velocity descent velocity in m/s or None to simulate descent on parachute
    @param parachute_parameters parachute parameters
    @param payload_weight payload weight in kg
    @param payload_area payload area in m^2
    @param model_data model data
    @param timestep time step in s
    @param initial_velocity initial velocity for descent on parachute in m/s

    @return segment_descent trajectory as gpxpy.gpx.GPXTrackSegment object
    @return landing_lon landing longitude in degrees
    @return landing_lat landing latitude in degrees
    """
    if descent_velocity is not None:
        assert(descent_velocity > 0)
        datetime_descent, alt_descent = equidistantAltitudeGrid(top_datetime, top_height, 0, -descent_velocity, timestep)
    else:
        time_descent, alt_descent, velocity_descent = parachute.parachuteDescent(top_height, timestep, payload_weight, parachute_parameters, payload_area, initial_velocity=initial_velocity)
        datetime_descent = top_datetime + np.array([datetime.timedelta(seconds=this_time) for this_time in time_descent])
    segment_descent = predictTrajectory(datetime_descent, alt_descent, model_data, top_lon, top_lat)
    if len(segment_descent.points) > 0:
        landing_lon = segment_descent.points[-1].longitude
        landing_lat = segment_descent.points[-1].latitude
    else:
        landing_lon = top_lon
        landing_lat = top_lat
    return segment_descent, landing_lon, landing_lat


def predictBalloonFlight(
        launch_datetime, launch_lon, launch_lat, launch_altitude,
        payload_weight, payload_area, ascent_velocity, top_height,
        parachute_parameters, model_data, timestep, 
        descent_velocity=None,
        descent_only=False,
        initial_velocity=0.):
    """
    Predict a balloon flight for given payload and launch parameters.

    @param launch_datetime datetime of launch
    @param launch_lon longitude of launch point in degrees
    @param launch_lat latitude of launch point in degrees
    @param launch_altitude altitude of launch point in m
    @param payload_weight payload weight in kg
    @param payload_area payload area in m^2
    @param ascent_velocity desired ascent velocity in m/s
    @param top_height balloon ceiling height in m
    @param parachute_parameters named array with parachute parameters
    @param model_data model data
    @param timestep time step in s
    @param descent_velocity desired descent velocity for descent on balloon (None for descent on parachute)
    @param descent_only whether to compute descent only (default: False)

    @return track trajectory as gpxpy.gpx.GPXTrack() object
    """

    track = gpxpy.gpx.GPXTrack()
    waypoints = []

    # Compute ascent
    if not descent_only:
        waypoints.append(gpxpy.gpx.GPXWaypoint(
                launch_lat, launch_lon, elevation=launch_altitude, time=launch_datetime, name='Launch'))
        segment_ascent, top_lon, top_lat, top_datetime = predictAscent(launch_datetime, launch_lon, launch_lat, launch_altitude, top_height, ascent_velocity, model_data, timestep)
        track.segments.append(segment_ascent)
    else:
        top_lon = launch_lon
        top_lat = launch_lat
        top_height = launch_altitude
        top_datetime = launch_datetime
    waypoints.append(gpxpy.gpx.GPXWaypoint(
            top_lat, top_lon, elevation=top_height, time=top_datetime, name='Burst'))

    # Compute descent.
    segment_descent, landing_lon, landing_lat = predictDescent(
            top_datetime, top_lon, top_lat, top_height, descent_velocity,
            parachute_parameters, payload_weight, payload_area, model_data, timestep,
            initial_velocity=initial_velocity)
    track.segments.append(segment_descent)
    waypoints.append(gpxpy.gpx.GPXWaypoint(
            landing_lat, landing_lon, elevation=segment_descent.points[-1].elevation, 
            time=segment_descent.points[-1].time, name='Landing'))

    # Add track description.
    flight_range = geog.distance([launch_lon, launch_lat], [landing_lon, landing_lat]) / 1000.
    track.description = 'Predicted balloon trajectory, ' + \
        ('' if descent_only else 'ascent velocity {:.1f} m/s, '.format(ascent_velocity)) + \
        'descent on parachute {}, '.format(parachute_parameters['name']) + \
        'flight range {:.0f} km'.format(flight_range)

    return track, waypoints, flight_range


def checkGeofence(cur_lon, cur_lat, launch_lon, launch_lat, radius):
    """
    Checks whether a given position is inside a geofence around the launch point.

    @param cur_lon longitude of current position in degrees
    @param cur_lat latitude of current position in degrees
    @param launch_lon longitude of launch point in degrees
    @param launch_lat latitude of launch point in degrees
    @param radius geofence radius in km

    @retval True point within geofence or radius unset
    @retval False point outside geofence
    """
    if radius:
        distance = geog.distance([launch_lon, launch_lat], [cur_lon, cur_lat]) / 1000.
        if distance > radius:
            logging.warning('Location outside geofence: {:.6f}?? {:.6f}?? distance {:.4f} km'.format(
                    cur_lon, cur_lat, distance))
            return False
        else:
            logging.debug('Distance to launch point: {:.4f} km'.format(distance))
            return True
    else:
        return True


def checkBorderCrossing(track):
    """
    Checks whether a flight track crosses a country border.

    @param track flight track as gpxpy.gpx.GPXTrack object
    @return is_abroad array of booleans indicating whether a track point is abroad
    @return foreign_countries array of iso codes of foreign countries crossed into
    """
    import countries
    borders_file = os.getenv('WORLD_BORDERS_FILE')
    if borders_file is None:
        borders_file = 'TM_WORLD_BORDERS-0.3.shp'
    cc = countries.CountryChecker(borders_file)
    no_of_points = 0
    for segment in track.segments:
        no_of_points += len(segment.points)
    country_list = np.zeros(no_of_points, dtype='S2')
    ind = 0
    for segment in track.segments:
        for point in segment.points:
            cpt = cc.getCountry(countries.Point(point.latitude, point.longitude))
            if cpt is None:
                country_list[ind] = '??'
            else:
                country_list[ind] = cpt.iso
            ind += 1
    assert(ind == len(country_list))
    is_abroad = (np.array(country_list) != country_list[0])
    foreign_countries = [country.decode('utf-8') for country in np.unique(country_list) if country != country_list[0]]
    return is_abroad, foreign_countries


def detectDescent(segment_tracked, launch_altitude):
    """
    Detect whether descent has begun (by cutting or bursting of the balloon).

    @param segment_tracked gpxpy.gpx.GPXTrackSegment() object with balloon track
    @param launch_altitude altitude of launch point in m

    @return index of highest point in track if descent detected, None if still on ascent
    """
    if len(segment_tracked.points) >= 3:
        last_heights = np.array([pkt.elevation for pkt in segment_tracked.points[-3:]])
        vertical_velocites = np.diff(last_heights)
        ind_max_height = np.argmax([pkt.elevation for pkt in segment_tracked.points])
        max_height = segment_tracked.points[ind_max_height].elevation
        if (vertical_velocites <= 0).all() and (max_height > launch_altitude + 100.): # If descent detected.
            return ind_max_height
        else:
            return None
    else:
        return None


def readCommSettings(filename):
    """
    Load communication settings from an ini file.
    """
    settings = {
            'connection': {
                    'type': 'rockblock',
                    'poll_time': 30
                    },
            'email': {
                    'host': None,
                    'user': None,
                    'password': None,
                    'from': '@rockblock.rock7.com'
                    },
            'rockblock': {
                    'user': None,
                    'password': None
                    },
            'file': {
                    'path': None,
                    'delimiter': '\t'
                    },
            'webserver': {
                    'protocol': None,
                    'host': None,
                    'user': None,
                    'password': None,
                    'directory': None,
                    'webpage': None,
                    'networklink': None,
                    'refreshinterval': None
                    },
            'output': {
                    'format': 'gpx',
                    'filename': 'trajectory.kml',
                    'directory': tempfile.gettempdir()
                    },
            'geofence': {
                    'radius': 0.
                    }
            }
    config = configparser.ConfigParser()
    config.read(filename)
    for section in config.sections():
        if section not in settings:
            settings[section] = {}
        for option in config.options(section):
            if option in settings[section]: # if a default value exists
                default_value = settings[section][option]
            else:
                default_value = None
            if isinstance(default_value,float):
                settings[section][option] = config[section].getfloat(option)
            elif isinstance(default_value,int):
                settings[section][option] = config[section].getint(option)
            elif isinstance(default_value,bool):
                settings[section][option] = config[section].getboolean(option)
            else:
                settings[section][option] = config[section].get(option)
    return settings


def messageHandlerFromSettings(settings):
    """
    Create a Message object corresponding to the given settings.
    """
    if settings['connection']['type'] == 'rockblock':
        if settings['email']['host'] is None or settings['email']['user'] is None or settings['email']['password'] is None:
            raise ValueError('Reception connection set to rockblock, but no complete email configuration is present.')
        message_handler = message_sbd.fromSettings(settings)
    elif settings['connection']['type'] == 'file':
        message_handler = message_file.fromSettings(settings)
        if settings['file']['path'] is None:
            raise ValueError('Reception connection set to file, but no file path is given.')
    else:
        raise ValueError('Unknown connection type: {}'.format(settings['connection']['type']))
    return message_handler


def liveForecast(
        launch_datetime, launch_lon, launch_lat, launch_altitude,
        payload_weight, payload_area, ascent_velocity, top_height,
        parachute_parameters,
        timestep, model_path, output_file,
        descent_velocity=None, 
        ini_file='comm.ini',
        kml_output=None):
    """
    Do a live forecast.

    @param launch_lon longitude of launch point in degrees
    @param launch_lat latitude of launch point in degrees
    @param launch_altitude altitude of launch point in m
    @param payload_weight payload weight in kg
    @param payload_area payload area in m^2
    @param ascent_velocity desired ascent velocity in m/s
    @param top_height balloon ceiling height in m
    @param parachute_parameters named array with parachute parameters
    @param timestep time step in s
    @param model_path directory where model data shall be stored
    @param output_file filename to which to write the resulting gpx or kml
    @param descent_velocity desired descent velocity for descent on balloon (None for descent on parachute)
    @param ini_file Configuration file for message retrieval and webserver upload (default: 'comm.ini')
    @param kml_output whether to output kml istead of gpx (overwritten by configuration file)
    """
    # Read communication configuration.
    settings = readCommSettings(ini_file)
    message_handler = messageHandlerFromSettings(settings)

    # Read model data.
    if launch_datetime is None:
        launch_datetime = utils.roundSeconds(datetime.datetime.utcnow())
    filelist = download_model_data.getGfsData(launch_lon, launch_lat, launch_datetime, model_path, timesteps=7)
    if filelist is None or len(filelist) == 0:
        logging.critical('Cannot download model data.')
        return
    model_data = readGfsDataFiles(filelist)

    # Do live prediction.
    logging.info('Starting live forecast. Waiting for messages ...')
    message_handler.connect()
    segment_tracked = gpxpy.gpx.GPXTrackSegment()
    is_ascending = True
    cur_lon = launch_lon
    cur_lat = launch_lat
    cur_alt = launch_altitude
    while True:
        try:
            messages = message_handler.getDecodedMessages()
            if len(messages) > 0:
                logging.info('Received {} message(s).'.format(len(messages)))
                logging.info('Last: {}'.format(messages[-1]))
                is_invalid = np.zeros(len(messages), dtype=bool)
                for ind_msg in range(len(messages)):
                    msg = messages[ind_msg]
                    if not checkGeofence(msg['LON'], msg['LAT'], launch_lon, launch_lat, settings['geofence']['radius']):
                        is_invalid[ind_msg] = True
                        continue
                    segment_tracked.points.append(message_handler.message2trackpoint(msg))
                if all(is_invalid):
                    msg = None
                    continue
                msg = np.array(messages)[~is_invalid][-1] # last valid message
                if is_ascending:
                    ind_top = detectDescent(segment_tracked, launch_altitude)
                    if ind_top is not None:
                        is_ascending = False
                        top_height = segment_tracked.points[ind_top].elevation
                        top_lon = segment_tracked.points[ind_top].longitude
                        top_lat = segment_tracked.points[ind_top].latitude
                        top_datetime = segment_tracked.points[ind_top].time
                        logging.info('Descent detected. Top altitude was at {:.0f} m.'.format(top_height))
                cur_lon = segment_tracked.points[-1].longitude
                cur_lat = segment_tracked.points[-1].latitude
                cur_alt = segment_tracked.points[-1].elevation
                cur_datetime = segment_tracked.points[-1].time
                if cur_alt > top_height:
                    logging.info('Balloon above top altitude. Assuming descent is imminent.')
                    is_ascending = False
                    top_lon = cur_lon
                    top_lat = cur_lat
                    top_height = cur_alt
                    top_datetime = cur_datetime
                waypoints = [gpxpy.gpx.GPXWaypoint(
                        segment_tracked.points[0].latitude,
                        segment_tracked.points[0].longitude,
                        elevation=segment_tracked.points[0].elevation,
                        time=segment_tracked.points[0].time,
                        name='Launch')]
                waypoints.append(message_handler.message2waypoint(msg, 'Current'))
                track = gpxpy.gpx.GPXTrack()
                track.segments.append(segment_tracked)
                if is_ascending:
                    # Track if balloon is cut now.
                    track_cut = deepcopy(track)
                    segment_cut, lon_cut, lat_cut = predictDescent(
                        cur_datetime, cur_lon, cur_lat, cur_alt, descent_velocity, 
                        parachute_parameters, payload_weight, payload_area, model_data, timestep)
                    track_cut.segments.append(segment_cut)
                    waypoints_cut = deepcopy(waypoints)
                    waypoints_cut.append(gpxpy.gpx.GPXWaypoint(
                        lat_cut, lon_cut,
                        elevation=segment_cut.points[-1].elevation,
                        time=segment_cut.points[-1].time, name='Landing (cut)'))
                    # Track if flight continues as planned.
                    segment_ascent, cur_lon, cur_lat, cur_datetime = predictAscent(cur_datetime, cur_lon, cur_lat, cur_alt, top_height, ascent_velocity, model_data, timestep)
                    track.segments.append(segment_ascent)
                    waypoints.append(gpxpy.gpx.GPXWaypoint(
                            cur_lat, cur_lon, elevation=top_height, time=cur_datetime, name='Ceiling'))
                    initial_velocity = 0.
                else:
                    waypoints.append(gpxpy.gpx.GPXWaypoint(
                            top_lat, top_lon, elevation=top_height, time=top_datetime, name='Ceiling'))
                    track_cut = None
                    initial_velocity = (segment_tracked.points[-1].elevation - segment_tracked.points[-2].elevation) / (segment_tracked.points[-1].time - segment_tracked.points[-2].time).total_seconds()
                segment_descent, landing_lon, landing_lat = predictDescent(
                        cur_datetime, cur_lon, cur_lat, top_height if is_ascending else cur_alt, descent_velocity, 
                        parachute_parameters, payload_weight, payload_area, model_data, timestep,
                        initial_velocity=initial_velocity)
                track.segments.append(segment_descent)
                waypoints.append(gpxpy.gpx.GPXWaypoint(
                        landing_lat, landing_lon,
                        elevation=segment_descent.points[-1].elevation,
                        time=segment_descent.points[-1].time, name='Landing'))
                if kml_output:
                    writeKml(track, os.path.join(settings['output']['directory'], output_file), waypoints=waypoints, networklink=settings['webserver']['networklink'], refreshinterval=settings['webserver']['refreshinterval'], upload=settings['webserver'] if settings['webserver']['protocol'] else None)
                    if track_cut:
                        writeKml(track_cut, os.path.join(settings['output']['directory'], os.path.splitext(output_file)[0]+'-cut.kml'), waypoints=waypoints_cut, upload=settings['webserver'] if settings['webserver']['protocol'] else None)
                else:
                    writeGpx(track, os.path.join(settings['output']['directory'], output_file), waypoints=waypoints, upload=settings['webserver'] if settings['webserver']['protocol'] else None)
                    if track_cut:
                        writeGpx(track_cut, os.path.join(settings['output']['directory'], os.path.splitext(output_file)[0]+'-cut.gpx'), waypoints=waypoints_cut, upload=settings['webserver'] if settings['webserver']['protocol'] else None)
                if settings['webserver']['webpage']:
                    if track_cut:
                        waypoints.append(waypoints_cut[-1]) # Add landing point for cutting balloon now.
                    createWebpage(track, waypoints, settings['webserver']['webpage'], upload=settings['webserver'] if settings['webserver']['protocol'] else None, track_cut=track_cut)
        except Exception as err:
            logging.critical('Exception occurred: {}'.format(traceback.format_exc()))
        time.sleep(settings['connection']['poll_time'])
            
    message_handler.disconnect()
    return


def hourlyForecast(
        launch_datetime, launch_lon, launch_lat, launch_altitude,
        payload_weight, payload_area, ascent_velocity, top_height,
        parachute_parameters,
        forecast_length,
        timestep, model_path, output_file,
        descent_velocity=None,
        webpage=None, upload=None):
    gpx = gpxpy.gpx.GPX()
    gpx.name = 'Hourly forecast'
    gpx.waypoints.append(gpxpy.gpx.GPXWaypoint(
            launch_lat, launch_lon, elevation=launch_altitude,
            name='Launch', description='Launch point'))
    hourly_segment = gpxpy.gpx.GPXTrackSegment()
    individual_tracks = []
    individual_waypoints = []
    if launch_datetime is None:
        launch_datetime = utils.roundHours(datetime.datetime.utcnow(), 1) # Round current time up to next full hour.
    for i_hour in range(forecast_length):
        filelist = download_model_data.getGfsData(launch_lon, launch_lat, launch_datetime, model_path)
        if filelist is None or len(filelist) == 0:
            break
        logging.info('Forecast for launch at {} ...'.format(launch_datetime))
        model_data = readGfsDataFiles(filelist)
        flight_track, flight_waypoints, flight_range = predictBalloonFlight(
            launch_datetime, launch_lon, launch_lat, launch_altitude,
            payload_weight, payload_area, ascent_velocity, top_height,
            parachute_parameters, model_data, timestep, 
            descent_velocity=descent_velocity, 
            descent_only=False)
        flight_track.name = 'Launch {}'.format(launch_datetime)
        flight_track.join(0)
        individual_tracks.append(flight_track)
        individual_waypoints.append(flight_waypoints)
        landing_lon = flight_track.segments[-1].points[-1].longitude
        landing_lat = flight_track.segments[-1].points[-1].latitude
        landing_alt = flight_track.segments[-1].points[-1].elevation
        flight_range = geog.distance([launch_lon, launch_lat], [landing_lon, landing_lat]) / 1000.
        duration = flight_track.segments[-1].points[-1].time - launch_datetime
        print('Launch {}: landing at {:.5f}?? {:.5f}?? {:.0f} m, range {:.1f} km, duration {}'.format(
                launch_datetime, landing_lon, landing_lat, landing_alt, flight_range, duration))
        gpx.waypoints.append(gpxpy.gpx.GPXWaypoint(
                landing_lat,
                landing_lon,
                elevation=landing_alt,
                time=launch_datetime,
                name='{}'.format(launch_datetime),
                description='Landing point for launch at {}, range {:.1f} km'.format(launch_datetime, flight_range)))
        hourly_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                landing_lat,
                landing_lon,
                elevation=landing_alt,
                time=launch_datetime))
        del model_data
        launch_datetime += datetime.timedelta(hours=1)
    if i_hour == 0:
        logging.error('No forecasts done due to missing data.')
        hourly_track = None
    else:
        hourly_track = gpxpy.gpx.GPXTrack(name='Landing points')
        hourly_track.segments.append(hourly_segment)
        gpx.tracks.append(hourly_track)
        for ind in range(forecast_length):
            gpx.tracks.append(individual_tracks[ind])
        writeGpx(gpx, output_file, upload=upload)
        if webpage:
            createWebpage(individual_tracks, individual_waypoints, webpage, hourly=gpx.waypoints, upload=upload)
    return hourly_track, individual_tracks, individual_waypoints


def writeGpx(track, output_file, waypoints=None, name=None, description=None, upload=None):
    """
    Write a trajectory to a GPX file.

    @param track gpxpy.gpx.GPXTrack object with trajectory or gpxpy.gpx.GPX object
    @param output_file the filename to which the track shall be written
    @param waypoints list of gpxpy.gpx.GPXWaypoint objects to be written as waypoints
    @param name name of the gpx
    @param description string to be written into the description field of the gpx file
    @param upload dictionary giving details of server upload, or None for no upload
    """
    if isinstance(track, gpxpy.gpx.GPX):
        gpx = track
    else:
        if name is None:
            name = 'Forecast {}'.format(track.get_time_bounds()[0])
        gpx = gpxpy.gpx.GPX()
        gpx.tracks.append(track)
        if waypoints:
            gpx.waypoints = waypoints
    gpx.creator = 'Balloon Operator'
    if name is not None:
        gpx.name = name
    if description is not None:
        gpx.description = description
    if upload:
        try:
            comm.uploadFile(upload, os.path.basename(output_file), gpx.to_xml())
        except Exception as err:
            logging.error('Error uploading file to {}: {}'.format(upload['host'], err))
    with open(output_file, 'w') as fd:
        logging.info('Writing {}'.format(output_file))
        fd.write(gpx.to_xml())
    return


def writeKml(track, output_file, waypoints=None, name=None, networklink=None, refreshinterval=None, upload=None):
    """
    Write a track to a KML file.

    @param track gpxpy.gpx.GPXTrack object with trajectory
    @param output_file the filename to which the track shall be written
    @param waypoints list of gpxpy.gpx.GPXWaypoint objects to be output as markers
    @param name name of the KML
    @param networklink URL to be added as network link in the KML
    @param refreshinterval interval in seconds to refresh the file over the network link
    @param upload dictionary giving details of server upload, or None for no upload
    """
    import simplekml
    coords = []
    for segment in track.segments:
        for point in segment.points:
            coords.append((point.longitude, point.latitude, point.elevation))
    if name is None:
        name = 'Forecast {}'.format(track.get_time_bounds()[0])
    kml = simplekml.Kml(name=name)
    if networklink:
        netlink = kml.newnetworklink(name='Network Link')
        netlink.link.href = networklink
        if refreshinterval is None:
            netlink.link.viewrefreshmode = 'onRequest'
        else:
            netlink.link.viewrefreshmode = 'onInterval'
            netlink.link.refreshinterval = refreshinterval
    lin = kml.newlinestring(
            name=track.name, description=track.description, coords=coords,
            tessellate=1, extrude=1, altitudemode=simplekml.AltitudeMode.absolute)
    if waypoints:
        for waypoint in waypoints:
            kml.newpoint(name=waypoint.name, coords=[(waypoint.longitude,waypoint.latitude,waypoint.elevation)])
    if upload:
        try:
            comm.uploadFile(upload, os.path.basename(output_file), kml.kml())
        except Exception as err:
            logging.error('Error uploading file to {}: {}'.format(upload['host'], err))
    logging.info('Writing {}'.format(output_file))
    kml.save(output_file)
    return


def gpxTrackToFolium(track):
    """
    Create a folium polyline object for a given gpx track segment.

    @param track gpxpy.gpx.GPXTrack or gpxpy.gpx.GPXTrackSegment object with track (segment)

    @return polyline folium.PolyLine object corresponding to the track segment
    """
    import folium
    track_points = []
    for segment in (track.segments if isinstance(track, gpxpy.gpx.GPXTrack) else [track]):
        for point in segment.points:
            track_points.append(tuple([point.latitude, point.longitude]))
    return folium.PolyLine(track_points)


def gpxWaypointToFolium(waypoint):
    """
    Convert a gpxpy waypoint to a folium marker.

    @param waypoint gpxpy.gpx.GPXWaypoint object with waypoint

    @return marker folium.Marker object corresponding to waypoint
    """
    import folium
    if waypoint.name.lower()=='launch':
        icon = folium.Icon(color='green', icon='play')
    elif waypoint.name.lower() in ['burst','ceiling']:
        icon = folium.Icon(color='blue', icon='certificate')
    elif waypoint.name.lower().startswith('landing'):
        icon = folium.Icon(color='orange', icon='stop')
    elif waypoint.name.lower()=='current':
        icon = folium.Icon(color='red', icon='record')
    else:
        icon = None
    return folium.Marker(
            (waypoint.latitude, waypoint.longitude), tooltip=waypoint.name,
            popup='<b>{}</b><br>{}Lon: {:.6f}??<br>Lat: {:.6f}??<br>Alt: {:.0f} m{}'.format(
                    waypoint.name, '{}<br>'.format(waypoint.time) if waypoint.time else '',
                    waypoint.longitude, waypoint.latitude, waypoint.elevation,
                    '<br>{}'.format(waypoint.description.replace('\n','<br>')) if waypoint.description else ''),
            icon=icon)


def createWebpage(track, waypoints, output_file, upload=None, hourly=None, track_cut=None):
    """
    Create an interactive webpage for the track, using the folium library.

    @param track flight track as gpxpy.gpx.GPXTrack object
    @param waypoints
    @param output_file
    @param upload
    @param hourly
    """
    import folium

    # Create map.
    if hourly:
        center_lat = np.mean([wp.latitude for wp in hourly])
        center_lon = np.mean([wp.longitude for wp in hourly])
    else:
        track_center = track.get_center()
        center_lat = track_center.latitude
        center_lon = track_center.longitude
    mymap = folium.Map(location=(center_lat, center_lon), tiles=None)
    # Provide a selection of background tiles.
    # For a comprehensive overview of available background tiles see
    # https://leaflet-extras.github.io/leaflet-providers/preview/
    folium.TileLayer('openstreetmap', name='OpenStreetMap').add_to(mymap)
    folium.TileLayer('Stamen Terrain', name='Stamen Terrain').add_to(mymap)
    folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            name='Esri WorldImagery',
            attr='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community').add_to(mymap)
    folium.TileLayer(
            'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}',
            name='US Imagery Topo',
            max_zoom=20,
            attr='Tiles courtesy of the <a href="https://usgs.gov/">U.S. Geological Survey</a>').add_to(mymap)
    folium.TileLayer(
            'https://map1.vis.earthdata.nasa.gov/wmts-webmerc/MODIS_Terra_CorrectedReflectance_TrueColor/default/{time}/{tilematrixset}{maxZoom}/{z}/{y}/{x}.{format}',
            name='Modis Terra TrueColor',
            min_zoom=1,
            max_zoom=9,
            format='jpg',
            time='',
            tilematrixset='GoogleMapsCompatible_Level',
            attr='Imagery provided by services from the Global Imagery Browse Services (GIBS), operated by the NASA/GSFC/Earth Science Data and Information System (<a href="https://earthdata.nasa.gov">ESDIS</a>) with funding provided by NASA/HQ.').add_to(mymap)
    folium.map.LayerControl().add_to(mymap)
    # Convert track(s)
    if hourly:
        assert (len(hourly) == len(track) + 1), 'Number of tracks does not correspond to number of clusters, {} + 1 != {}.'.format(len(track), len(hourly))
        gpxWaypointToFolium(hourly[0]).add_to(mymap)
        for ind in range(len(track)):
            folium.Marker(
                    (hourly[ind+1].latitude, hourly[ind+1].longitude),
                    tooltip=hourly[ind+1].name, popup=hourly[ind+1].description).add_to(mymap)
            gpxTrackToFolium(track[ind]).add_to(mymap)
    else:
        for segment in track.segments:
            gpxTrackToFolium(segment).add_to(mymap)
        if track_cut:
            gpxTrackToFolium(track_cut).add_to(mymap)
        for waypoint in waypoints:
            gpxWaypointToFolium(waypoint).add_to(mymap)
    # Export result.
    mymap.fit_bounds(mymap.get_bounds())
    if upload:
        try:
            comm.uploadFile(upload, os.path.basename(output_file), mymap.get_root().render())
        except Exception as err:
            logging.error('Error uploading file to {}: {}'.format(upload['host'], err))
    else:
        mymap.save(output_file)
        logging.info('Created {}.'.format(output_file))
    return


def exportImage(track, output_file, waypoints=None, bb=None):
    """
    Export an image file with a map and the predicted track.

    @param track gpxpy.gpx.GPXTrack object with trajectory
    @param output_file the filename to which the map shall be written
    @param waypoints list of gpxpy.gpx.GPXWaypoint objects to be included in the map
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    # Prepare data.
    lons = []
    lats = []
    for segment in track.segments:
        for point in segment.points:
            lons.append(point.longitude)
            lats.append(point.latitude)
    launch_lat = track.segments[0].points[0].latitude
    launch_lon = track.segments[0].points[0].longitude
    launch_time = track.segments[0].points[0].time

    if bb is None:
        lon_range, lat_range = download_model_data.getModelArea(lons[0], lats[0], radius=300.)
        bb = lon_range + lat_range

    # Do plot.
    plt.figure(figsize=(8,8))
    ax = plt.axes(projection=ccrs.Stereographic(central_latitude=launch_lat, central_longitude=launch_lon))
    ax.set_extent(bb, crs=ccrs.PlateCarree())
    ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
    ax.add_feature(cfeature.LAND)
    ax.add_feature(cfeature.OCEAN)
    ax.add_feature(cfeature.LAKES)
    ax.add_feature(cfeature.RIVERS)
    ax.add_feature(cfeature.COASTLINE, edgecolor=cfeature.COLORS['water'])
    ax.add_feature(cfeature.BORDERS, edgecolor='red')
    plt.plot(lons, lats, transform=ccrs.Geodetic(), color='#00AA00')
    if waypoints is not None:
        for waypoint in waypoints:
            if waypoint.name.lower()=='launch':
                color = 'black'
            elif waypoint.name.lower() in ['burst','ceiling']:
                color = 'white'
            elif waypoint.name.lower().startswith('landing'):
                color = 'red'
            else:
                color = None
            plt.plot(waypoint.longitude, waypoint.latitude, transform=ccrs.Geodetic(), marker='o', color=color)
    plt.title('Balloon trajectory forecast for {}'.format(launch_time.strftime('%d %b %Y %H:%M UTC')))
    logging.info('Writing {}'.format(output_file))
    plt.savefig(output_file, dpi=300)
    plt.close()
    return


def exportTsv(track, output_file, top_height=None, is_abroad=None, foreign_countries=None):
    """
    Export a track in tabular separated values (tsv) ASCII format.

    @param track gpxpy.gpx.GPXTrack object with trajectory
    @param output_file the filename to which data shall be written
    @param top_height the ceiling altitude of the flight
    @param is_abroad a boolean array indicating if track points are in a foreign country
    @param foreign_countries an array of foreign countries the track crosses into
    """
    launch_point = track.segments[0].points[0]
    landing_point = track.segments[-1].points[-1]
    flight_range = geog.distance((launch_point.longitude, launch_point.latitude), (landing_point.longitude, landing_point.latitude)) / 1000.
    azimuth = geog.course((launch_point.longitude, launch_point.latitude), (landing_point.longitude, landing_point.latitude), bearing=True)
    logging.info('Writing tsv file {}'.format(output_file))
    with open(output_file, 'w') as fd:
        fd.write('Launch: {} UTC\n'.format(launch_point.time.strftime('%d %b %Y %H:%M')))
        fd.write('Landing: {:.4f}??N, {:.4f}??E at {} UTC\n'.format(landing_point.latitude, landing_point.longitude, landing_point.time.strftime('%H:%M')))
        fd.write('Distance: {:.0f} km, azimuth: {:.0f}??\n'.format(flight_range, azimuth))
        if top_height is not None:
            fd.write('Max. altitude: {:.0f} m\n'.format(top_height))
        if is_abroad is None:
            try:
                is_abroad, foreign_countries = checkBorderCrossing(track)
            except Exception as err:
                logging.warning('Cannot check border crossing: {}\nIs WORLD_BORDERS_FILE pointing to the data file?'.format(err))
        if isinstance(is_abroad, np.ndarray):
            if is_abroad.any():
                if foreign_countries is None:
                    fd.write('Border is crossed.')
                else:
                    fd.write('Border is crossed into {}.\n'.format(', '.join(foreign_countries)))
            else:
                fd.write('Border is not crossed.\n')
        fd.write('\n')
        fd.write('Time (UTC)\tLongitude (??E)\tLatitude (??N)\tAltitude (m)\n')
        for segment in track.segments:
            for point in segment.points:
                fd.write('{}\t{:.4f}\t{:.4f}\t{:.0f}\n'.format(point.time.strftime('%H:%M:%S'), point.longitude, point.latitude, point.elevation))
    return


def main(launch_datetime, config_file='flight.ini', descent_only=False, hourly=False, live=None, launch_pos=None, output_file=None, kml_output=None, webpage=None, image=None, bb=None, tsv=None, upload=None):
    """
    Main function to make a trajectory prediction from a configuration file.

    @param launch_datetime
    @param config_file ini file to use (default: 'flight.ini')
    @param descent_only whether to compute descent only (default: False)
    @param launch_pos launch position (longitude, latitude, altitude[, speed]), overwrites
        position in ini file if specified
    @param output_file output filename for computed trajectory (default: '/tmp/trajectory.gpx')
    @param hourly whether to do an hourly forecast, showing landing spots for diffent launch times (default: False)
    @param live whether to do a live forecast, computation continuation of trajectory from tracker on balloon
    @param kml_output output result in KML format instead of GPX, optionally embedding a network link
    @param webpage create an interactive web page displaying the trajectory and write it to given file name
    @param upload upload data to foreign host according to information in given ini file
    """
    # Read configuration.
    config = configparser.ConfigParser()
    config.read(config_file)
    payload_weight = config['payload'].getfloat('payload_weight')
    assert(payload_weight is not None)
    payload_area = config['payload'].getfloat('payload_area')
    if 'ascent_balloon_weight' in config['payload']:
        ascent_balloon_weight = config['payload'].getint('ascent_balloon_weight')
    else:
        ascent_balloon_weight = config['payload'].getint('balloon_weight')
    assert(ascent_balloon_weight is not None)
    descent_balloon_weight = config['payload'].getint('descent_balloon_weight', fallback=None)
    ascent_velocity = config['payload'].getfloat('ascent_velocity')
    assert(ascent_velocity is not None)
    descent_velocity = config['payload'].getfloat('descent_velocity', fallback=None)
    fill_gas = filling.fillGas(config['payload']['fill_gas'])
    cut_altitude = config['payload'].getfloat('cut_altitude', fallback=None)
    balloon_parameter_list = filling.readBalloonParameterList(config['parameters']['balloon'])
    ascent_balloon_parameters = filling.lookupParameters(balloon_parameter_list, ascent_balloon_weight)
    if descent_balloon_weight is not None:
        descent_balloon_parameters = filling.lookupParameters(balloon_parameter_list, descent_balloon_weight)
    else:
        descent_balloon_parameters = None
    parachute_parameter_list = parachute.readParachuteParameterList(config['parameters']['parachute'])
    parachute_parameters = parachute.lookupParachuteParameters(parachute_parameter_list, config['payload']['parachute_type'])
    initial_velocity = 0.
    if launch_pos is None:
        launch_lon = config['launch_site'].getfloat('longitude')
        launch_lat = config['launch_site'].getfloat('latitude')
        launch_altitude = config['launch_site'].getfloat('altitude')
    else:
        launch_lon = launch_pos[0]
        launch_lat = launch_pos[1]
        launch_altitude = launch_pos[2]
        if len(launch_pos) >= 4:
            initial_velocity = -launch_pos[3]
    timestep = config['parameters'].getint('timestep')
    if 'model_path' in config['parameters']:
        model_path = config['parameters']['model_path']
    else:
        model_path = tempfile.gettempdir()

    if output_file is None:
        if hourly:
            output_file = 'hourly_prediction'
        else:
            output_file = 'trajectory'
        if kml_output:
            output_file += '.kml'
        else:
            output_file += '.gpx'
        output_file = os.path.join(tempfile.gettempdir(), output_file)

    if upload:
        cfg_upload = configparser.ConfigParser()
        cfg_upload.read(upload)
        upload = cfg_upload['webserver']

    # Compute balloon performance. This is only needed once, even for multiple
    # forecasts with different launch time.
    if descent_velocity is not None: # If it's a two-balloon flight with descent on balloon.
        ascent_launch_radius, descent_launch_radius, ascent_neutral_lift, descent_neutral_lift, \
        ascent_burst_height, descent_burst_height = filling.twoBalloonFilling(
            ascent_balloon_parameters, descent_balloon_parameters, payload_weight, 
            ascent_velocity, descent_velocity, fill_gas=fill_gas)
        assert(cut_altitude is not None)
        if descent_burst_height < cut_altitude + 1000: # 1000m safety margin
            raise ValueError('Descent balloon bursts before reaching top altitude: burst height {:.0f} m, cut altitude {:.0f} m'.format(descent_burst_height, cut_altitude))
        if ascent_burst_height < cut_altitude + 2000:
            raise ValueError('Ascent balloon bursts before ascent balloon (accounting for safety margin): {:.0f} m < {:.0f} m + 2000 m'.format(descent_burst_height, ascent_burst_height))
        top_height = cut_altitude
    else: # If it's a normal balloon flight with descent on parachute.
        ascent_launch_radius, ascent_neutral_lift, ascent_burst_height = filling.balloonFilling(
                ascent_balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas)
        top_height = ascent_burst_height
        if cut_altitude is not None:
            if cut_altitude < ascent_burst_height:
                top_height = cut_altitude
            else:
                logging.warning('Warning: cut altitude larger than burst height, {:.1f}m > {:.1f}m.'.format(cut_altitude, ascent_burst_height))
        descent_launch_radius = None
        descent_neutral_lift = None
        descent_burst_height = None

    # Predict trajectory.
    if live: # Live forecast.
        liveForecast(
            launch_datetime, launch_lon, launch_lat, launch_altitude,
            payload_weight, payload_area, ascent_velocity, top_height,
            parachute_parameters,
            timestep, model_path, output_file,
            descent_velocity=descent_velocity, 
            ini_file=live,
            kml_output=kml_output)

    elif hourly: # Hourly landing site forecast.
        hourlyForecast(
            launch_datetime, launch_lon, launch_lat, launch_altitude,
            payload_weight, payload_area, ascent_velocity, top_height,
            parachute_parameters,
            hourly,
            timestep, model_path, output_file,
            descent_velocity=descent_velocity,
            webpage=webpage, upload=upload)

    else: # Normal trajectory computation.
        # Download and read in model data.
        model_filenames = download_model_data.getGfsData(launch_lon, launch_lat, launch_datetime, model_path)
        if model_filenames is None or len(model_filenames) == 0:
            logging.error('Error retrieving model data.')
            return
        model_data = readGfsDataFiles(model_filenames)
    
        # Do prediction.
        track, waypoints, flight_range = predictBalloonFlight(
            launch_datetime, launch_lon, launch_lat, launch_altitude,
            payload_weight, payload_area, ascent_velocity, top_height,
            parachute_parameters, model_data, timestep, 
            descent_velocity=descent_velocity, 
            descent_only=descent_only,
            initial_velocity=initial_velocity)
        if ascent_launch_radius is not None:
            print('Ascent balloon: fill volume {:.3f} m^3, neutral lift {:.3f} kg, burst height {:.0f} m'.format(4./3.*np.pi*ascent_launch_radius**3, ascent_neutral_lift, ascent_burst_height))
        if descent_velocity is not None:
            print('Descent balloon: fill volume {:.3f} m^3, neutral lift {:.3f} kg, burst height {:.0f} m'.format(4./3.*np.pi*descent_launch_radius**3, descent_neutral_lift, descent_burst_height))
        print('Landing point: {:.5f}?? {:.5f}?? {:.0f} m, range {:.0f} km'.format(
                track.segments[-1].points[-1].longitude,
                track.segments[-1].points[-1].latitude,
                track.segments[-1].points[-1].elevation,
                flight_range))
    
        # Write out track.
        if kml_output:
            writeKml(track, output_file, waypoints=waypoints, networklink=kml_output if isinstance(kml_output,str) else None, upload=upload)
        else:
            writeGpx(track, output_file, waypoints=waypoints, description=track.description, upload=upload)
        if webpage:
            createWebpage(track, waypoints, webpage, upload=upload)
        if image:
            exportImage(track, image, waypoints=waypoints, bb=bb)
        if tsv:
            exportTsv(track, tsv, top_height=top_height)

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser('Balloon trajectory predictor')
    parser.add_argument('launchtime', help='Launch date and time (UTC) dd-mm-yyyy HH:MM:SS')
    parser.add_argument('-i', '--ini', required=False, default='flight.ini', help='Configuration ini file name (default: flight.ini)')
    parser.add_argument('-p', '--position', required=False, default=None, help='Start position lon,lat,alt[,speed]')
    parser.add_argument('-d', '--descent-only', required=False, action='store_true', default=False, help='Descent only')
    parser.add_argument('-t', '--timely', required=False, type=int, default=None, help='Do hourly prediction and show landing sites for given number of hours')
    parser.add_argument('-l', '--live', required=False, nargs='?', default=None, const='comm.ini', help='Do a live prediction')
    parser.add_argument('-k', '--kml', required=False, nargs='?', default=None, const=True, help='Create output in KML format, optionally with network link')
    parser.add_argument('-w', '--webpage', required=False, default=None, help='Create interactive web page with track and export to file')
    parser.add_argument('-g', '--image', required=False, default=None, help='Create an image of a map with the track')
    parser.add_argument('-b', '--bb', required=False, default=None, help='Bounding box for map')
    parser.add_argument('-x', '--export-tsv', required=False, default=None, help='Export trajectory in tsv format')
    parser.add_argument('-u', '--upload', required=False, default=None, help='Upload results to web server')
    parser.add_argument('-o', '--output', required=False, default=None, help='Output file name')
    parser.add_argument('--log', required=False, default='INFO', help='Log level')
    args = parser.parse_args()
    if args.launchtime == 'now':
        launch_datetime = utils.roundSeconds(datetime.datetime.utcnow())
    else:
        launch_datetime = datetime.datetime.fromisoformat(args.launchtime)
    if args.position is not None:
        launch_pos = np.array(args.position.split(',')).astype(float)
    else:
        launch_pos = None
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: {}'.format(args.log))
    logging.basicConfig(level=numeric_level)
    main(launch_datetime, config_file=args.ini, launch_pos=launch_pos, descent_only=args.descent_only, hourly=args.timely, live=args.live, output_file=args.output, kml_output=args.kml, webpage=args.webpage, image=args.image, bb=args.bb, tsv=args.export_tsv, upload=args.upload)
