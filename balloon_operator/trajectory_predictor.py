#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 18 19:42:53 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import curve_fit
import pygrib
import datetime
import gpxpy
import gpxpy.gpx
import srtm
import geog
import configparser
import argparse
from balloon_operator import filling, parachute, download_model_data, constants, utils


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


def readGfsData(filename):
    """
    Read in GFS data file

    @param filename name of GFS GRIB data file
    @return model_data a dictionary with the model data with the following keys:
        'press', 'lon', 'lat', 'surface_pressure', 'surface_altitude',
        'u_wind_deg', 'v_wind_deg'
    """
    grbidx = pygrib.open(filename)
    # Get levels in GRIB file. Assume all variables have same order of levels.
    levels = []
    for grb in grbidx:
        if grb.name == 'U component of wind':
            levels.append(grb.level)
            lat, lon = grb.latlons()
            lat = lat[:,0]
            lon = lon[0,:]
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
            print('Unused variable: {}'.format(grb.name))
    grbidx.close()
    # Convert winds from m/s to deg/s
    for ind_level in range(len(levels)):
        u_wind[ind_level, :, :], v_wind[ind_level, :, :] = m2deg(lon, lat, u_wind[ind_level, :, :], v_wind[ind_level, :, :])
    return {'press': np.array(levels)*100., 'lon': lon, 'lat': lat, # convert levels from hPa to Pa
            'surface_pressure': surface_pressure, 'surface_altitude': surface_altitude, 
            'altitude': altitude, 'u_wind_deg': u_wind, 'v_wind_deg': v_wind}


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
    burst_datetime = start_datetime + datetime.timedelta(seconds=duration)
    datetime_vector = start_datetime + np.array([datetime.timedelta(seconds=seconds) for seconds in np.arange(0, duration, timestep)])
    altitude_vector = np.arange(start_altitude, end_altitude, ascent_velocity*timestep)
    assert(len(datetime_vector) == len(altitude_vector))
    datetime_vector = np.append(datetime_vector, burst_datetime)
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
    expfun = lambda x,a,b: a*np.exp(b*x)
    popt, pcov = curve_fit(expfun,  model_data['altitude'][:, i_start, j_start],  model_data['press'],  p0=(model_data['surface_pressure'][i_start, j_start], -1./8300.))
    pressure = expfun(altitude, popt[0], popt[1])
    max_model_press = np.max(model_data['press'])
    min_model_press = np.min(model_data['press'])
    pressure[pressure > max_model_press] = max_model_press # Cap pressures larger than maximum of model grid to avoid extrapolation.
    pressure[pressure < min_model_press] = min_model_press # Cap pressures lower than maximum of model grid to avoid extrapolation.
    # Displace balloon by model winds.
    lon = lon_start
    lat = lat_start
    interp_u = RegularGridInterpolator((model_data['press'],model_data['lon'],model_data['lat']), model_data['u_wind_deg'])
    interp_v = RegularGridInterpolator((model_data['press'],model_data['lon'],model_data['lat']), model_data['v_wind_deg'])
    has_landed = False
    for ind in range(len(dt)):
        if ind > 0:
            delta_t = (dt[ind] - dt[ind-1]).total_seconds()
            u = interp_u([pressure[ind], lon, lat])[0]
            v = interp_v([pressure[ind], lon, lat])[0]
            lon += delta_t * u
            lat += delta_t * v
            surface_elevation = srtm.get_elevation(lat, lon)
            if surface_elevation is not None and altitude[ind] <= surface_elevation:
                # Compute after which fraction of the last time step the ground
                # has been hit, and go back this time step.
                # This approach assumes no steep slopes.
                below_ground = surface_elevation - altitude[ind]
                timestep_fraction = below_ground / (altitude[ind] - altitude[ind-1])
                lon -= timestep_fraction * delta_t * u
                lat -= timestep_fraction * delta_t * v
                dt -= datetime.timedelta(seconds=timestep_fraction*delta_t)
                print('Reached surface: {} {} {}'.format(lon, lat, altitude[ind], surface_elevation))
                has_landed = True
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                lat, lon, elevation=altitude[ind], time=dt[ind], 
                comment='{:.2f} hPa'.format(pressure[ind]/100.)))
        if has_landed:
            break
    return gpx_segment


def predictBalloonFLight(
        launch_lon, launch_lat, launch_altitude, launch_datetime,
        payload_weight, payload_area, ascent_velocity, 
        balloon_parameters, parachute_parameters, fill_gas, 
        model_data, timestep, 
        descent_only=False, cut_altitude=None):

    track = gpxpy.gpx.GPXTrack()

    # Compute balloon performance and ascent.
    if not descent_only:
        launch_radius, free_lift, burst_height = filling.balloonFilling(
                balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas)
        if cut_altitude is not None:
            if cut_altitude < burst_height:
                burst_height = cut_altitude
            else:
                print('Warning: cut altitude larger than burst height, {:.1f}m > {:.1f}m.'.format(cut_altitude, burst_height))

        datetime_ascent, alt_ascent = equidistantAltitudeGrid(launch_datetime, launch_altitude, burst_height, ascent_velocity, timestep)
        segment_ascent = predictTrajectory(datetime_ascent, alt_ascent, model_data, launch_lon, launch_lat)
        burst_lon = segment_ascent.points[-1].longitude
        burst_lat = segment_ascent.points[-1].latitude
        burst_datetime = datetime_ascent[-1]
        burst_datetime = utils.roundSeconds(burst_datetime, 1) # round up to next full second
        track.segments.append(segment_ascent)
    else:
        burst_lon = launch_lon
        burst_lat = launch_lat
        burst_height = launch_altitude
        burst_datetime = launch_datetime
        launch_radius = None
        free_lift = None

    # Compute descent.
    time_descent, alt_descent, velocity_descent = parachute.parachuteDescent(burst_height, timestep, payload_weight, parachute_parameters, payload_area)
    datetime_descent = burst_datetime + np.array([datetime.timedelta(seconds=this_time) for this_time in time_descent])
    segment_descent = predictTrajectory(datetime_descent, alt_descent, model_data, burst_lon, burst_lat)
    landing_lon = segment_descent.points[-1].longitude
    landing_lat = segment_descent.points[-1].latitude
    track.segments.append(segment_descent)

    # Add track description.
    flight_range = geog.distance([launch_lon, launch_lat], [landing_lon, landing_lat]) / 1000.
    track.description = 'Predicted balloon trajectory, ' + \
        ('' if descent_only else 'ascent velocity {:.1f} m/s, '.format(ascent_velocity)) + \
        'descent on parachute {}, '.format(parachute_parameters['name']) + \
        'flight range {:.0f} km'.format(flight_range)

    return track, launch_radius, free_lift


def writeGpx(track, output_file, description=None):
    """
    Write a trajectory to a GPX file.

    @param track gpxpy.gpx.GPXTrack object with trajectory
    @param output_file
    """
    gpx = gpxpy.gpx.GPX()
    gpx.creator = 'Balloon Operator'
    gpx.name = 'Forecast {}'.format(track.get_time_bounds()[0])
    if description is not None:
        gpx.description = description
    gpx.tracks.append(track)
    with open(output_file, 'w') as fd:
        print('Writing {}'.format(output_file))
        fd.write(gpx.to_xml())
    return


def main(launch_datetime, config_file='flight.ini', descent_only=False, launch_pos=None, output_file='/tmp/trajectory.gpx'):
    """
    Main function to make a trajectory prediction from a configuration file.
    """
    # Read configuration.
    config = configparser.ConfigParser()
    config.read(config_file)
    payload_weight = config['payload'].getfloat('payload_weight')
    assert(payload_weight is not None)
    payload_area = config['payload'].getfloat('payload_area')
    balloon_weight = config['payload'].getint('balloon_weight')
    assert(balloon_weight is not None)
    ascent_velocity = config['payload'].getfloat('ascent_velocity')
    assert(ascent_velocity is not None)
    fill_gas = filling.fillGas(config['payload']['fill_gas'])
    cut_altitude = config['payload'].getfloat('cut_altitude', None)
    balloon_parameter_list = filling.readBalloonParameterList(config['parameters']['balloon'])
    balloon_parameters = filling.lookupParameters(balloon_parameter_list, balloon_weight)
    parachute_parameter_list = parachute.readParachuteParameterList(config['parameters']['parachute'])
    parachute_parameters = filling.lookupParameters(parachute_parameter_list, config['payload']['parachute_type'], key='name')
    if launch_pos is None:
        launch_lon = config['launch_site'].getfloat('longitude')
        launch_lat = config['launch_site'].getfloat('latitude')
        launch_altitude = config['launch_site'].getfloat('altitude')
    else:
        launch_lon = launch_pos[0]
        launch_lat = launch_pos[1]
        launch_altitude = launch_pos[2]
    timestep = config['parameters'].getint('timestep')
    model_path = config['parameters']['model_path']

    # Download and read in model data.
    model_filename = download_model_data.getGfsData(launch_lon, launch_lat, launch_datetime, model_path)
    if model_filename is None:
        print('Error retrieving model data.')
        return
    model_data = readGfsData(model_filename)

    track, launch_radius, free_lift = predictBalloonFLight(
        launch_lon, launch_lat, launch_altitude, launch_datetime,
        payload_weight, payload_area, ascent_velocity, 
        balloon_parameters, parachute_parameters, fill_gas, 
        model_data, timestep, 
        descent_only=descent_only, cut_altitude=cut_altitude)
    if launch_radius is not None:
        print('Fill volume {:.4f} m^3, free lift {:.3f} kg'.format(4./3.*np.pi*launch_radius**3, free_lift))

    # Write out track as GPX.
    writeGpx(track, output_file, description=track.description)

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('launchtime', help='Launch date and time (UTC) dd-mm-yyyy HH:MM:SS')
    parser.add_argument('-i', '--ini', required=False, default='flight.ini', help='Configuration ini file name (default: flight.ini)')
    parser.add_argument('-p', '--position', required=False, default=None, help='Start position lon,lat,alt')
    parser.add_argument('-d', '--descent-only', required=False, action='store_true', default=False, help='Descent only')
    parser.add_argument('-o', '--output', required=False, default='/tmp/trajectory.gpx', help='Output file')
    args = parser.parse_args()
    launch_datetime = datetime.datetime.fromisoformat(args.launchtime)
    if args.position is not None:
        launch_pos = np.array(args.position.split(',')).astype(float)
    else:
        launch_pos = None
    main(launch_datetime, config_file=args.ini, launch_pos=launch_pos, descent_only=args.descent_only, output_file=args.output)
