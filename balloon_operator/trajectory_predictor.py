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
                print('Reached surface: {:.6f}° {:.6f}° {:.0f} m'.format(lon, lat, altitude[ind], surface_elevation))
                has_landed = True
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                lat, lon, elevation=altitude[ind], time=dt[ind], 
                comment='{:.2f} hPa'.format(pressure[ind]/100.)))
        if has_landed:
            break
    return gpx_segment


def predictBalloonFlight(
        launch_lon, launch_lat, launch_altitude, launch_datetime,
        payload_weight, payload_area, ascent_velocity, 
        ascent_balloon_parameters, fill_gas, parachute_parameters, 
        model_data, timestep, 
        descent_velocity=None, descent_balloon_parameters=None,
        cut_altitude=None, descent_only=False):
    """
    Predict a balloon flight for given payload and launch parameters.

    @param launch_lon longitude of launch point
    @param launch_lat latitude of launch point
    @param launch_altitude altitude of launch point
    @param launch_datetime datetime of launch
    @param payload_weight payload weight in kg
    @param payload_area payload area in m^2
    @param ascent_velocity desired ascent velocity in m/s
    @param ascent_balloon_parameters balloon parameters
    @param fill_gas fill gas
    @param parachute_parameters parachute parameters
    @param model_data model data
    @param timestep timestep
    @param descent_velocity desired descent velocity for descent on balloon (None for descent on parachute)
    @param descent_balloon_parameters parameters of descent balloon
    @param cut_altitude altitude to activate the cutter to enter descent
    @param descent_only whether to compute descent only (default: False)

    @return track trajectory as gpxpy.gpx.GPXTrack() object
    @return ascent_launch_radius launch radius of ascent balloon
    @return ascent_neutral_lift neutral lift of ascent balloon
    @return ascent_burst_height burst height of ascent balloon
    @return descent_launch_radius launch radius of descent balloon (None if not present)
    @return descent_neutral_lift neutral lift of descent balloon (None if not present)
    @return descent_burst_height burst height of descent balloon (None if not present)
    """

    track = gpxpy.gpx.GPXTrack()

    # Compute balloon performance.
    if descent_velocity is not None: # if it's a two-balloon flight with descent on balloon
        ascent_launch_radius, descent_launch_radius, ascent_neutral_lift, descent_neutral_lift, \
        ascent_burst_height, descent_burst_height = filling.twoBalloonFilling(
            ascent_balloon_parameters, descent_balloon_parameters, payload_weight, 
            ascent_velocity, descent_velocity, fill_gas=fill_gas)
        assert(cut_altitude is not None)
        if descent_burst_height < cut_altitude + 1000: # 1000m safety margin
            raise ValueError('Descent balloon bursts before reaching top altitude: burst height {:.0f} m, cut altitude {:.0f} m'.format(descent_burst_height, cut_altitude))
        if ascent_burst_height < cut_altitude + 2000:
            raise ValueError('Ascent balloon bursts before ascent balloon (accounting for safety margin): {:.0f} m < {:.0f} m + 2000 m'.format(descent_burst_height, ascent_burst_height))
    else:
        ascent_launch_radius, ascent_neutral_lift, ascent_burst_height = filling.balloonFilling(
                ascent_balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas)
        descent_launch_radius = None
        descent_neutral_lift = None
        descent_burst_height = None

    # Compute ascent
    if not descent_only:
        top_height = ascent_burst_height
        if cut_altitude is not None:
            if cut_altitude < ascent_burst_height:
                top_height = cut_altitude
            else:
                print('Warning: cut altitude larger than burst height, {:.1f}m > {:.1f}m.'.format(cut_altitude, ascent_burst_height))

        datetime_ascent, alt_ascent = equidistantAltitudeGrid(launch_datetime, launch_altitude, top_height, ascent_velocity, timestep)
        segment_ascent = predictTrajectory(datetime_ascent, alt_ascent, model_data, launch_lon, launch_lat)
        burst_lon = segment_ascent.points[-1].longitude
        burst_lat = segment_ascent.points[-1].latitude
        burst_datetime = datetime_ascent[-1]
        burst_datetime = utils.roundSeconds(burst_datetime, 1) # round up to next full second
        track.segments.append(segment_ascent)
    else:
        burst_lon = launch_lon
        burst_lat = launch_lat
        top_height = launch_altitude
        burst_datetime = launch_datetime

    # Compute descent.
    if descent_velocity is not None:
        assert(descent_velocity > 0)
        datetime_descent, alt_descent = equidistantAltitudeGrid(burst_datetime, top_height, 0, -descent_velocity, timestep)
    else:
        time_descent, alt_descent, velocity_descent = parachute.parachuteDescent(top_height, timestep, payload_weight, parachute_parameters, payload_area)
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

    return track, ascent_launch_radius, ascent_neutral_lift, ascent_burst_height, \
        descent_launch_radius, descent_neutral_lift, descent_burst_height


def writeGpx(track, output_file, name=None, description=None):
    """
    Write a trajectory to a GPX file.

    @param track gpxpy.gpx.GPXTrack object with trajectory or gpxpy.gpx.GPX object
    @param output_file the filename to which the track shall be written
    @param description string to be written into the description field of the gpx file
    """
    if isinstance(track, gpxpy.gpx.GPX):
        gpx = track
    else:
        if name is None:
            name = 'Forecast {}'.format(track.get_time_bounds()[0])
        gpx = gpxpy.gpx.GPX()
        gpx.tracks.append(track)
    gpx.creator = 'Balloon Operator'
    if name is not None:
        gpx.name = name
    if description is not None:
        gpx.description = description
    with open(output_file, 'w') as fd:
        print('Writing {}'.format(output_file))
        fd.write(gpx.to_xml())
    return


def main(launch_datetime, config_file='flight.ini', descent_only=False, hourly=False, launch_pos=None, output_file=None):
    """
    Main function to make a trajectory prediction from a configuration file.

    @param launch_datetime
    @param config_file ini file to use (default: 'flight.ini')
    @param descent_only whether to compute descent only (default: False)
    @param launch_pos launch position (longitude, latitude, altitude), overwrites
        position in ini file if specified
    @param output_file output filename for computed trajectory (default: '/tmp/trajectory.gpx')
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
    descent_balloon_weight = config['payload'].getint('ascent_balloon_weight', fallback=None)
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

    if output_file is None:
        if hourly:
            output_file = '/tmp/hourly_prediction.gpx'
        else:
            output_file = '/tmp/trajectory.gpx'

    if hourly: # Hourly landing site forecast.
        forecast_length = hourly
        gpx = gpxpy.gpx.GPX()
        gpx.name = 'Hourly forecast'
        hourly_track = gpxpy.gpx.GPXTrack()
        hourly_segment = gpxpy.gpx.GPXTrackSegment()
        dt = utils.roundHours(datetime.datetime.utcnow(), 1) # Round current time up to next full hour.
        for i_hour in range(forecast_length):
            filename = download_model_data.getGfsData(launch_lon, launch_lat, dt, model_path)
            if filename is None:
                break
            model_data = readGfsData(filename)
            flight_track, ascent_launch_radius, ascent_neutral_lift, ascent_burst_height, \
            descent_launch_radius, descent_neutral_lift, descent_burst_height = predictBalloonFlight(
                launch_lon, launch_lat, launch_altitude, launch_datetime,
                payload_weight, payload_area, ascent_velocity, 
                ascent_balloon_parameters, fill_gas, parachute_parameters, 
                model_data, timestep, 
                descent_velocity=descent_velocity, 
                descent_balloon_parameters=descent_balloon_parameters,
                cut_altitude=cut_altitude)
            landing_lon = flight_track.segments[-1].points[-1].longitude
            landing_lat = flight_track.segments[-1].points[-1].latitude
            landing_alt = flight_track.segments[-1].points[-1].elevation
            flight_range = geog.distance([launch_lon, launch_lat], [landing_lon, landing_lat]) / 1000.
            print('Launch {}: landing at {:.5f}° {:.5f}° {:.0f} m, range {:.1f} km'.format(
                    dt, landing_lon, landing_lat, landing_alt, flight_range))
            gpx.waypoints.append(gpxpy.gpx.GPXWaypoint(
                    landing_lat,
                    landing_lon,
                    elevation=landing_alt,
                    time=dt,
                    name='{}'.format(dt),
                    description='Launch at {}, range {:.1f} km'.format(dt, flight_range)))
            hourly_segment.points.append(gpxpy.gpx.GPXTrackPoint(
                    landing_lat,
                    landing_lon,
                    elevation=landing_alt,
                    time=dt))
            dt += datetime.timedelta(hours=1)
        hourly_track.segments.append(hourly_segment)
        gpx.tracks.append(hourly_track)
        writeGpx(gpx, output_file)

    else: # Normal trajectory computation.
        # Download and read in model data.
        model_filename = download_model_data.getGfsData(launch_lon, launch_lat, launch_datetime, model_path)
        if model_filename is None:
            print('Error retrieving model data.')
            return
        model_data = readGfsData(model_filename)
    
        # Do prediction.
        track, ascent_launch_radius, ascent_neutral_lift, ascent_burst_height, \
        descent_launch_radius, descent_neutral_lift, descent_burst_height = predictBalloonFlight(
            launch_lon, launch_lat, launch_altitude, launch_datetime,
            payload_weight, payload_area, ascent_velocity, 
            ascent_balloon_parameters, fill_gas, parachute_parameters, 
            model_data, timestep, 
            descent_velocity=descent_velocity, 
            descent_balloon_parameters=descent_balloon_parameters,
            cut_altitude=cut_altitude, descent_only=descent_only)
        if ascent_launch_radius is not None:
            print('Ascent balloon: fill volume {:.3f} m^3, neutral lift {:.3f} kg, burst height {:.0f} m'.format(4./3.*np.pi*ascent_launch_radius**3, ascent_neutral_lift, ascent_burst_height))
        if descent_velocity is not None:
            print('Descent balloon: fill volume {:.3f} m^3, neutral lift {:.3f} kg, burst height {:.0f} m'.format(4./3.*np.pi*descent_launch_radius**3, descent_neutral_lift, descent_burst_height))
        print('Landing point: {:.5f}° {:.5f}° {:.0f} m'.format(
                track.segments[-1].points[-1].longitude,
                track.segments[-1].points[-1].latitude,
                track.segments[-1].points[-1].elevation))
    
        # Write out track as GPX.
        writeGpx(track, output_file, description=track.description)

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('launchtime', help='Launch date and time (UTC) dd-mm-yyyy HH:MM:SS')
    parser.add_argument('-i', '--ini', required=False, default='flight.ini', help='Configuration ini file name (default: flight.ini)')
    parser.add_argument('-p', '--position', required=False, default=None, help='Start position lon,lat,alt')
    parser.add_argument('-d', '--descent-only', required=False, action='store_true', default=False, help='Descent only')
    parser.add_argument('-t', '--timely', required=False, type=int, default=None, help='Do hourly prediction and show landing sites for given number of hours')
    parser.add_argument('-o', '--output', required=False, default=None, help='Output file')
    args = parser.parse_args()
    launch_datetime = datetime.datetime.fromisoformat(args.launchtime)
    if args.position is not None:
        launch_pos = np.array(args.position.split(',')).astype(float)
    else:
        launch_pos = None
    main(launch_datetime, config_file=args.ini, launch_pos=launch_pos, descent_only=args.descent_only, hourly=args.timely, output_file=args.output)
