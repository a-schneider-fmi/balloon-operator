#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module to download model data for a specified region.

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
import requests
import datetime
import os.path
import pathlib
import pyproj
import logging
import tempfile
import argparse
from balloon_operator import utils


def getLonLatArea(launch_lon, launch_lat, resolution=0.25, radius=500.):
    """
    Determine lon-lat area in which the flight is expected to take place.
    This is used to determine the area in which to download the model data.
    Current implementation uses a box that contains a circle around the launch
    place with given radius.

    @param launch_lon longitude of launch point in degrees
    @param launch_lat latitude of launch point in degrees
    @param resolution box resolution in degrees (default: 0.25)
    @param radius radius in km around the launch point (default: 500)

    @return lon_range longitude range [min, max] in which to download model data
    @return lat_range latitude range [min, max] in which to download model data
    """
    pos_bottom = utils.geoPropagate(launch_lon, launch_lat, 180, radius*1000.)
    pos_top = utils.geoPropagate(launch_lon, launch_lat, 0, radius*1000.)
    pos_left = utils.geoPropagate(launch_lon, launch_lat, 270, radius*1000.)
    pos_right = utils.geoPropagate(launch_lon, launch_lat, 90, radius*1000.)
    lon_range = [np.floor(pos_left[0]/resolution)*resolution, np.ceil(pos_right[0]/resolution)*resolution]
    lat_range = [np.floor(pos_bottom[1]/resolution)*resolution, np.ceil(pos_top[1]/resolution)*resolution]
    return lon_range, lat_range


def getModelRun(launch_datetime, run_period=6, forecast_period=1):
    """
    Determine latest model run / forecast for planned launch time.

    @param launch_datetime datetime of the launch
    @param run_period period in hours in which model runs are performed (default: 6)
    @param forecast_period period in hours in which forecasts are written out (default: 1)

    @return model_datetime datetime of the latest model run
    @return forecast_time forecast time in hours
    """
    model_datetime = datetime.datetime.utcnow()
    if launch_datetime < model_datetime: # if launch is in the past
        model_datetime = launch_datetime
    new_hour = (model_datetime.hour // run_period) * run_period # runs every run_period hours
    model_datetime = datetime.datetime.combine(model_datetime.date(), datetime.time(new_hour))
    forecast_time = ((launch_datetime - model_datetime) // datetime.timedelta(hours=forecast_period)) * forecast_period
    return model_datetime, forecast_time


def modelFilename(model_name, lon_range, lat_range, run_datetime, forecast_time, model_resolution=None, format='grb2'):
    """
    This function encapsulates the local filename for model data for given 
    model, cut-out, run, forecast

    @param model_name name of the model, e.g. gfs
    @param lon_range longitude range [lon_start, lon_end]
    @param lat_range latitude range [lat_start, lat_end]
    @param model_datetime datetime of the model run
    @param forecast_time forecast time (as int)
    @param model_resolution model resolution
    @param format file extension indicating the format, default: 'grb2'

    @return filename
    """
    return '{}{}_{}-{}_{}-{}_{}{}.{}'.format(
            model_name, model_resolution if model_resolution is not None else '',
            lon_range[0], lon_range[1], lat_range[0], lat_range[1],
            run_datetime.strftime('%Y%m%dt%H') if run_datetime is not None else '',
            'f{:03d}'.format(forecast_time) if forecast_time is not None else '',
            format)


def urlGfs(lon_range, lat_range, model_datetime, forecast_time, model_resolution=0.25):
    """
    Determine download URL for specified subset of GFS data from NOAA server.

    @param lon_range longitude range [lon_start, lon_end] to download
    @param lat_range latitude range [lat_start, lat_end] to download
    @param model_datetime datetime of the model run to download
    @param forecast_time forecast time (as int)
    @param model_resolution model resolution to download

    @return url download URL
    """
    # Download URL obtained from https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl
    url = 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_{}.pl?file=gfs.t{}z.pgrb2.{}.f{:03d}'.format(
            '{:.02f}'.format(model_resolution).replace('.','p'), model_datetime.strftime('%H'), 
            '{:.02f}'.format(model_resolution).replace('.','p'), forecast_time) \
        +'&lev_surface=on&lev_1000_mb=on&lev_975_mb=on&lev_950_mb=on&lev_925_mb=on' \
        +'&lev_900_mb=on&lev_850_mb=on&lev_800_mb=on&lev_750_mb=on&lev_700_mb=on' \
        +'&lev_650_mb=on&lev_600_mb=on&lev_550_mb=on&lev_500_mb=on&lev_450_mb=on' \
        +'&lev_400_mb=on&lev_350_mb=on&lev_300_mb=on&lev_250_mb=on&lev_200_mb=on' \
        +'&lev_150_mb=on&lev_100_mb=on&lev_70_mb=on&lev_50_mb=on&lev_40_mb=on' \
        +'&lev_30_mb=on&lev_20_mb=on&lev_10_mb=on&lev_7_mb=on&lev_5_mb=on' \
        +'&lev_3_mb=on&lev_2_mb=on&lev_1_mb=on' \
        +'&var_PRES=on&var_HGT=on&var_UGRD=on&var_VGRD=on' \
        +'&subregion=&leftlon={}&rightlon={}'.format(lon_range[0], lon_range[1]) \
        +'&bottomlat={}&toplat={}'.format(lat_range[0], lat_range[1]) \
        +'&dir=%2Fgfs.{}%2Fatmos'.format(model_datetime.strftime('%Y%m%d%%2F%H'))
    return url


def urlHarmonieFmi(lon_range, lat_range, starttime=None, duration=4, format='GRIB2'):
    """
    Determine download URL for specified subset of HARMONIE Scandinavia data from smartmet.fmi.fi.
    This server is only accessible from FMI's intranet.

    @param lon_range longitude range [lon_start, lon_end] to download
    @param lat_range latitude range [lat_start, lat_end] to download
    @param starttime datetime of the model run to download (None for latest)
    @param duration hours until endtime (default: 4)
    @param format output format ('GRIB2', 'netcdf')

    @return url download URL
    """
    url = 'http://smartmet.fmi.fi/download?producer=harmonie_skandinavia_mallipinta' \
        +'&format={}&param=Pressure,GeomHeight,Temperature,WindUMS,WindVMS'.format(format) \
        +'&bbox={},{},{},{}'.format(lon_range[0], lat_range[0], lon_range[1], lat_range[1])
    if starttime is not None:
        url += '&starttime={}'.format(starttime.strftime('%Y-%m-%dT%H:%M'))
        endtime = starttime + datetime.timedelta(hours=duration)
        url += '&endtime={}'.format(endtime.strftime('%Y-%m-%dT%H:%M'))
    else:
        url += '&timesteps={}'.format(duration) # assuming one timestep per hour
    return url


def urlHarmonieMetno(model_datetime, time_range=None, x_range=None, y_range=None, hybrid_range=None):
    """
    Determine URL for OPeNDAP retrieval of HARMONIE Scandinavia data from
    MET Norway Thredds Service

    @param model_datetime datetime of the model run to download

    @return url OPeNDAP URL
    """
    url = 'https://thredds.met.no/thredds/dodsC/mepslatest/meps_det_2_5km_{}Z.ncml'.format(model_datetime.strftime('%Y%m%dT%H'))
    if time_range is not None and x_range is not None and y_range is not None:
        t_range_str = f'[{time_range[0]}:1:{time_range[1]}]' if time_range is not None else '[:]'
        x_range_str = f'[{x_range[0]}:1:{x_range[1]}]' if x_range is not None else '[:]'
        y_range_str = f'[{y_range[0]}:1:{y_range[1]}]' if y_range is not None else '[:]'
        hybrid_range_str = f'[{hybrid_range[0]}:1:{hybrid_range[1]}]' if hybrid_range is not None else '[:]'
        param = '?forecast_reference_time,projection_lambert' \
            + f',time{t_range_str},x{x_range_str},y{y_range_str},hybrid{hybrid_range_str}' \
            + f',ap{hybrid_range_str},b{hybrid_range_str}' \
            + f',longitude{y_range_str}{x_range_str}' \
            + f',latitude{y_range_str}{x_range_str}' \
            + f',air_pressure_at_sea_level{t_range_str}[0:1:0]{y_range_str}{x_range_str}' \
            + f',surface_air_pressure{t_range_str}[0:1:0]{y_range_str}{x_range_str}' \
            + f',air_temperature_ml{t_range_str}{hybrid_range_str}{y_range_str}{x_range_str}' \
            + f',specific_humidity_ml{t_range_str}{hybrid_range_str}{y_range_str}{x_range_str}' \
            + f',x_wind_ml{t_range_str}{hybrid_range_str}{y_range_str}{x_range_str}' \
            + f',y_wind_ml{t_range_str}{hybrid_range_str}{y_range_str}{x_range_str}'
        url += param
    return url


def checkFmiConnectivity():
    """
    Check whether FMI's SmartMet server is reachable.
    This is only the case from FMI's intranet.
    """
    try:
        response = requests.get('http://smartmet.fmi.fi', timeout=(10,10))
        return True
    except requests.exceptions.ConnectTimeout:
        return False
    except Exception as err:
        logging.error('Unknown error while trying to connect to SmartMet server: {}'.format(err))
    return False


def downloadData(url, filename):
    """
    Download data from a server.

    @param url URL from where to download
    @param filename full path where to save the data

    @return filename if successful, None on error
    """
    if os.path.isfile(filename): 
        logging.info('File {} already downloaded.'.format(filename))
        return filename
    else:
        logging.info('Trying to download {} from {} ...'.format(filename, url))
        count = 0
        failure = True
        while failure and count < 3:
            try:
                response = requests.get(url)
                failure = False
            except Exception as err:
                logging.error('Error downloading model data: {}'.format(err))
                failure = True
            count += 1
        if failure:
            return None
        else:
            if response.text.startswith('<!DOCTYPE html PUBLIC'): # Error web page
                return None
            else:
                dest_dir = os.path.dirname(filename)
                if dest_dir and not os.path.isdir(dest_dir):
                    pathlib.Path(dest_dir).mkdir(parents=True, exist_ok=True)
                try:
                    with open(filename, 'wb') as fd:
                        fd.write(response.content)
                except Exception as err:
                    logging.error('Error writing local file: {}'.format(err))
                logging.info('Downloaded {}.'.format(filename))
                return filename


def downloadOpendapData(url, filename):
    """
    Download a dataset via OPeNDAP

    @param url Download URL
    @param filename local filename to write the downloaded file to
    """
    import xarray
    try:
        ds = xarray.open_dataset(url, engine='pydap')
        ds.to_netcdf(filename)
    except Exception as err:
        logging.error(f'Error retrieving data from {url}: {err}')
        return None
    return filename


def downloadGfsData(lon_range, lat_range, model_datetime, forecast_time, dest_dir, model_resolution=0.25):
    """
    Download specified subset of GFS data from NOAA server.

    @param lon_range longitude range [lon_start, lon_end] to download
    @param lat_range latitude range [lat_start, lat_end] to download
    @param model_datetime datetime of the model run to download
    @param forecast_time forecast time (as int)
    @param dest_dir directory in which to put the downloaded file
    @param model_resolution model resolution to download

    @return filename name of the downloaded file, or None if the requested data is not available
    """
    url = urlGfs(lon_range, lat_range, model_datetime, forecast_time, model_resolution)
    filename = os.path.join(dest_dir,modelFilename('gfs', lon_range, lat_range, model_datetime, forecast_time, model_resolution=model_resolution))
    return downloadData(url, filename)


def downloadHarmonieFmiData(lon_range, lat_range, model_datetime, dest_dir, duration=4, format='GRIB2'):
    """
    Download specified subset of HARMONIE Scandinavia data from smartmet.fmi.fi.
    This server is only accessible from FMI's intranet.

    @param lon_range longitude range [lon_start, lon_end] to download
    @param lat_range latitude range [lat_start, lat_end] to download
    @param model_datetime datetime of the model run to download
    @param dest_dir directory in which to put the downloaded file
    @param duration duration in hours which to include in the model data (default: 4)
    """
    url = urlHarmonieFmi(lon_range, lat_range, starttime=model_datetime, duration=duration, format=format)
    file_extension = {'GRIB2': 'grb2', 'netcdf': 'nc'}
    filename = os.path.join(dest_dir,modelFilename('harmonie', lon_range, lat_range, model_datetime, None, format=file_extension[format]))
    if os.path.isfile(filename.replace('{}','')):
        return filename
    else:
        if checkFmiConnectivity():
            return downloadData(url, filename)
        else:
            logging.error("No connectivity to FMI's SmartMet server.")
            return None


def determineHarmonieMetnoRange(ds, launch_lon, launch_lat, launch_datetime, duration=4, radius=500.):
    """
    Determine region of intererst in HARMONIE MetNo data

    @return t_range time range [ind_t_start, ind_t_end]
    @return x_range x range [ind_x_start, ind_x_end]
    @return y_range y range [ind_y_start, ind_y_end]
    @return hybrid_range hybrid range [ind_hybrid_start, ind_hybrid_end]
    """
    proj = pyproj.Proj('+proj=lcc +lon_0={} +lat_0={} +lat_1={} +lat_2={} +R={}'.format(
            ds['projection_lambert'].longitude_of_central_meridian,
            ds['projection_lambert'].latitude_of_projection_origin,
            ds['projection_lambert'].standard_parallel[0],
            ds['projection_lambert'].standard_parallel[1],
            ds['projection_lambert'].earth_radius))
    times = np.array([datetime.datetime.fromtimestamp(ts) for ts in ds['time'][:]])
    delta_t = np.array([dt - launch_datetime if dt >= launch_datetime else launch_datetime - dt for dt in times])
    ind_t = np.argmin(delta_t)
    delta_t = np.array([(dt - times[ind_t]).total_seconds() for dt in times[ind_t:]])
    ind_t_end = ind_t + np.argmin(np.abs(delta_t - duration*3600))
    x_launch, y_launch = proj(launch_lon, launch_lat)
    ind_x_start = np.argmin(np.abs(ds['x'][:].data - (x_launch - radius*1000.)))
    ind_x_end = np.argmin(np.abs(ds['x'][:].data - (x_launch + radius*1000.)))
    ind_y_start = np.argmin(np.abs(ds['y'][:].data - (y_launch - radius*1000.)))
    ind_y_end = np.argmin(np.abs(ds['y'][:].data - (y_launch + radius*1000.)))
    return [ind_t, ind_t_end], [ind_x_start, ind_x_end], [ind_y_start, ind_y_end], [0, len(ds['hybrid'])-1]


def getGfsData(launch_lon, launch_lat, launch_datetime, dest_dir, model_resolution=0.25, timesteps=4, run_interval=6):
    """
    Download GFS data around a given launch location for a given launch datetime.

    @param launch_lon longitude of the launch site
    @param launch_lat latitude of the launch site
    @param launch_datetime datetime of the launch
    @param dest_dir directory to which model data shall be downloaded
    @param model_resolution model resolution in degrees (default 0.5)
    @param timesteps number of forecasts to download (default: 4)
    @param run_interval interval in hours in which model runs are performed (default: 6)

    @return filelist a list of filenames (inclusive path) of the downloaded files, or None if unsuccessful
    """
    lon_range, lat_range = getLonLatArea(launch_lon, launch_lat, resolution=model_resolution)
    gfs_datetime, forecast_time = getModelRun(launch_datetime)
    for i_try in range(10):
        filename = downloadGfsData(lon_range, lat_range, gfs_datetime, forecast_time, dest_dir, model_resolution=model_resolution)
        if filename is not None:
            break
        gfs_datetime -= datetime.timedelta(hours=run_interval)
        forecast_time += run_interval
    if filename is None:
        filelist = []
        return filelist
    else:
        filelist = [filename]
    for delta_t in range(1,timesteps):
        filename = downloadGfsData(lon_range, lat_range, gfs_datetime, forecast_time+delta_t, dest_dir, model_resolution=model_resolution)
        if filename is not None:
            filelist.append(filename)
    return filelist


def getHarmonieMetnoData(launch_lon, launch_lat, launch_datetime, dest_dir, duration=4):
    """
    Obtain HARMONIE data around a given launch location for a given launch datetime
    from MET Norway's open data server and cache them into netCDF files.

    @param launch_lon longitude of the launch site
    @param launch_lat latitude of the launch site
    @param launch_datetime datetime of the launch
    @param dest_dir directory to which model data shall be downloaded
    @param duration duration in hours which to include in the model data (default: 4)

    @return filename the filename (inclusive path) of the downloaded file, or None if unsuccessful
    """
    from pydap.client import open_url

    # Determine latest run available.
    run_interval=3
    model_datetime, _ = getModelRun(launch_datetime, run_period=run_interval)
    ds = None
    for i_try in range(5):
        url = urlHarmonieMetno(model_datetime)
        try:
            ds = open_url(url)
        except requests.exceptions.HTTPError as err:
            logging.debug(f'{url} not found: {err}')
            model_datetime -= datetime.timedelta(hours=run_interval)
            continue
        except Exception as err:
            logging.error(f'Exception occurred while trying to obtain data from {url}: {err}')
            continue
        break
    if ds is None:
        logging.error('Current model data not found on server.')

    # Determine region of interest to download.
    start_datetime = utils.roundHours(launch_datetime, 60)
    t_range, x_range, y_range, hybrid_range = determineHarmonieMetnoRange(ds, launch_lon, launch_lat, start_datetime, duration=duration)

    # Download to file, if not present.
    filename = os.path.join(dest_dir,modelFilename('harmonie', x_range, y_range, model_datetime, t_range[0], format='hdf'))
    if not os.path.exists(filename):
        url = urlHarmonieMetno(model_datetime, t_range, x_range, y_range, hybrid_range)
        logging.debug(f'Download URL: {url}')
        filename = downloadOpendapData(url, filename)
    return [filename]


def getHarmonieFmiData(launch_lon, launch_lat, launch_datetime, dest_dir, duration=4):
    """
    Download HARMONIE data around a given launch location for a given launch datetime
    from FMI's internal server.

    @param launch_lon longitude of the launch site
    @param launch_lat latitude of the launch site
    @param launch_datetime datetime of the launch
    @param dest_dir directory to which model data shall be downloaded
    @param duration duration in hours which to include in the model data (default: 4)

    @return filename the filename (inclusive path) of the downloaded file, or None if unsuccessful
    """
    lon_range, lat_range = getLonLatArea(launch_lon, launch_lat)
    model_datetime = utils.roundHours(launch_datetime, 60)
    filelist = []
    for delta_t in range(duration):
        filename = downloadHarmonieFmiData(lon_range, lat_range, model_datetime+datetime.timedelta(hours=delta_t), dest_dir, duration=0)
        if filename is not None:
            filelist.append(filename)
    return filelist


def getModelData(model_name, launch_lon, launch_lat, launch_datetime, dest_dir, duration=4):
    """
    Download model data.
    """
    if model_name.upper() == 'GFS':
        return getGfsData(launch_lon, launch_lat, launch_datetime, dest_dir, timesteps=duration)
    elif model_name.upper() == 'HARMONIE':
        return getHarmonieMetnoData(launch_lon, launch_lat, launch_datetime, dest_dir, duration=duration)
    elif model_name.upper() == 'HARMONIE-FMI':
        return getHarmonieFmiData(launch_lon, launch_lat, launch_datetime, dest_dir, duration=duration)
    else:
        logging.error('Unknown model: {}'.format(model_name))
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser('Model data downloader')
    parser.add_argument('lon', type=float, help='Launch longitude')
    parser.add_argument('lat', type=float, help='Launch latitude')
    parser.add_argument('launchtime', help='Launch date and time (UTC) dd-mm-yyyy HH:MM:SS')
    parser.add_argument('-m', '--model', required=False, default='gfs', help='Select model (gfs, harmonie)')
    parser.add_argument('-d', '--dest-dir', required=False, default=tempfile.gettempdir(), help='Destination directory')
    parser.add_argument('--log', required=False, default='INFO', help='Log level')
    args = parser.parse_args()
    if args.launchtime == 'now':
        launch_datetime = utils.roundSeconds(datetime.datetime.utcnow())
    else:
        launch_datetime = datetime.datetime.fromisoformat(args.launchtime)
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: {}'.format(args.log))
    logging.basicConfig(level=numeric_level)
    getModelData(args.model, args.lon, args.lat, launch_datetime, args.dest_dir)
