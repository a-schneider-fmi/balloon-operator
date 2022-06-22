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
import geog
import logging


def getModelArea(launch_lon, launch_lat, resolution=0.25, radius = 800.):
    """
    Determine lon-lat area in which the flight is expected to take place.
    This is used to determine the area in which to download the model data.
    Current implementation uses a box that contains a 800 km circle around the
    launch place.

    @param launch_lon longitude of launch point in degrees
    @param launch_lat latitude of launch point in degrees
    @param resolution model resolution in degrees (default: 0.25)
    @param radius radius in km around the launch point (default: 800)

    @return lon_range longitude range [min, max] in which to download model data
    @return lat_range latitude range [min, max] in which to download model data
    """
    pos_bottom = geog.propagate((launch_lon, launch_lat), 180, radius*1000., bearing=True)
    pos_top = geog.propagate((launch_lon, launch_lat), 0, radius*1000., bearing=True)
    pos_left = geog.propagate((launch_lon, launch_lat), 270, radius*1000., bearing=True)
    pos_right = geog.propagate((launch_lon, launch_lat), 90, radius*1000., bearing=True)
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


def modelFilename(model_name, lon_range, lat_range, run_datetime, forecast_time, model_resolution=0.25):
    """
    This function encapsulates the local filename for model data for given 
    model, cut-out, run, forecast

    @param model_name name of the model, e.g. gfs
    @param lon_range longitude range [lon_start, lon_end]
    @param lat_range latitude range [lat_start, lat_end]
    @param model_datetime datetime of the model run
    @param forecast_time forecast time (as int)
    @param model_resolution model resolution

    @return filename
    """
    return '{}{}_{}-{}_{}-{}_{}f{:03d}.grb2'.format(
            model_name, model_resolution, 
            lon_range[0], lon_range[1], lat_range[0], lat_range[1], 
            run_datetime.strftime('%Y%m%dt%H'), forecast_time)

def downloadGfs(lon_range, lat_range, model_datetime, forecast_time, dest_dir, model_resolution=0.25):
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
    filename = os.path.join(dest_dir,modelFilename('gfs', lon_range, lat_range, model_datetime, forecast_time, model_resolution))

    if os.path.isfile(filename): 
        logging.info('File {} already downloaded.'.format(filename))
        return filename
    else:
        logging.info('Trying to download {} ...'.format(filename))
        count = 0
        result = None
        while result is None and count < 3:
            try:
                response = requests.get(url)
                result = response.text
            except Exception as err:
                logging.error('Error downloading GFS data: {}'.format(err))
                result = None
            count += 1
        if result is None:
            return None
        else:
            if result.startswith('<!DOCTYPE html PUBLIC'): # Error web page
                return None
            else:
                if not os.path.isdir(dest_dir):
                    pathlib.Path(dest_dir).mkdir(parents=True, exist_ok=True)
                try:
                    with open(filename, 'wb') as fd:
                        fd.write(response.content)
                except Exception as err:
                    logging.error('Error writing local file: {}'.format(err))
                logging.info('Downloaded {}.'.format(filename))
                return filename


def getGfsData(launch_lon, launch_lat, launch_datetime, dest_dir, model_resolution=0.25, timesteps=4):
    """
    Download GFS data around a given launch location for a given launch datetime.

    @param launch_lon longitude of the launch site
    @param launch_lat latitude of the launch site
    @param launch_datetime datetime of the launch
    @param dest_dir directory to which model data shall be downloaded
    @param model_resolution model resolution in degrees (default 0.5)
    @param timesteps number of forecasts to download (default: 4)

    @return filename the filename (inclusive path) of the downloaded file, or None if unsuccessful
    """
    lon_range, lat_range = getModelArea(launch_lon, launch_lat, resolution=model_resolution)
    gfs_datetime, forecast_time = getModelRun(launch_datetime)
    for i_try in range(10):
        filename = downloadGfs(lon_range, lat_range, gfs_datetime, forecast_time, dest_dir, model_resolution=model_resolution)
        if filename is not None:
            break
        gfs_datetime -= datetime.timedelta(hours=6)
        forecast_time += 6
    if filename is None:
        filelist = []
        return filelist
    else:
        filelist = [filename]
    for delta_t in range(1,timesteps):
        filename = downloadGfs(lon_range, lat_range, gfs_datetime, forecast_time+delta_t, dest_dir, model_resolution=model_resolution)
        if filename is not None:
            filelist.append(filename)
    return filelist
