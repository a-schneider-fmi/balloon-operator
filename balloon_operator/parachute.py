#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module to compute descent on parachute.

The computation is based on Jens Söder's BalloonTrajectory MATLAB program.

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
from balloon_operator import filling


def readParachuteParameterList(filename):
    """
    Read parachute parameter table (name, diameter, drag coefficient) from
    CSV file.

    @param filename CSV file name of the data

    @return named array with parachute parameters, names are 'name', 'diameter', 'drag_coefficient'
    """
    return np.genfromtxt(
            filename, delimiter='\t', skip_header=1,
            names=['name', 'diameter', 'drag_coefficient'],
            dtype=['U25', 'f8', 'f8'])


def lookupParachuteParameters(parameter_list, name):
    """
    Look up parachute parameters for a given name.

    @param parameter_list parameter table as named array, e.g. as read with readParachuteParameterList
    @param name name to look up the data

    @return selected column of the named array, or None if the given weight is not in the list.
    """
    return filling.lookupParameters(parameter_list, name, key='name')


def parachuteDescent(alt_start, timestep, payload_weight, parachute_parameters, payload_area, payload_drag_coefficient=0.25, initial_velocity=0.):
    """
    Compute descent on parachute by solving the equation of motion.

    This is a port of the descent function in Jens Söder's BalloonTrajectory
    MATLAB program.

    @param alt_start start altitude in m
    @param timestep time step of the output arrays in seconds
    @param payload_weight payload weight in kg
    @param parachute_parameters parachute parameters as given by lookupParachuteParameters
    @param payload_area payload area in m^2
    @param payload_drag_coefficient drag coefficient of payload (default 0.25)

    @return time array of time relative to begin of descent in s
    @return altitude array of altitudes in m
    @return velocity array of velocities in m/s
    """

    # Initialise variables.
    t = 0
    z = alt_start;
    s = initial_velocity

    delt=.2

    # Atmospheric constants:
    M = 0.02896 # molar mass of air in kg/mol
    R = 8.314 # gas-constant in J/(K*mol)
    Rs = 287 # specific gas constant of (dry) air
    rhoa = 1.225 # air density at 15°C, 1013 hPa (see ICAO) in kg/m^3s
    g = 9.81 # gravitational constant in m/s^2

    T = 248.6 # temperature after CIRA86 for 50°N

    # Equation of motion:
    # hdd+g-1/(2*m)*rhog*exp(-M*g*h/(R*T)*(cdpara*paraarea+cdbox*boxarea)*hd^2=0

    # Use Runge-Kutta-Algorithm to solve DEq.
    H = T*Rs/g

    cdpara = parachute_parameters['drag_coefficient']
    paraarea = np.pi*parachute_parameters['diameter']**2/4.
    cdbox = payload_drag_coefficient
    boxarea = payload_area
    m = payload_weight
    max_iter = 10000000
    time = np.zeros(max_iter)
    altitude = np.zeros(max_iter)
    velocity = np.zeros(max_iter)
    for i in range(max_iter):
        if z < 0:
            break # Interrupt integration when reaching groundlevel.

        k1z = s
        k1s = -g+1/(2*m)*rhoa*np.exp(-z/H)*(cdpara*paraarea+cdbox*boxarea)*s**2

        k2z = s+delt/2*k1s
        k2s = -g+1/(2*m)*rhoa*np.exp(-(z+delt/2*k1z)/H)*(cdpara*paraarea+cdbox*boxarea)*(s+delt/2*k1s)**2

        k3z = s+delt/2*k2s
        k3s = -g+1/(2*m)*rhoa*np.exp(-(z+delt/2*k2z)/H)*(cdpara*paraarea+cdbox*boxarea)*(s+delt/2*k2s)**2

        k4z = s+delt*k3s;
        k4s = -g+1/(2*m)*rhoa*np.exp(-(z+delt*k3z)/H)*(cdpara*paraarea+cdbox*boxarea)*(s+delt*k3s)**2

        zn = z+delt/6*(k1z+2*k2z+2*k3z+k4z)
        sn = s+delt/6*(k1s+2*k2s+2*k3s+k4s)

        time[i] = t
        altitude[i] = z
        velocity[i] = s

        t = t + delt;
        z = zn;
        s = sn;
        if i == max_iter-1:
            raise ValueError('DEQ-solver in parachuteDescent did not terminate!')

    time = time[:i] # Cut remaining unfilled entries.
    altitude = altitude[:i]
    velocity = velocity[:i]

    # Downsample data array.
    if len(time) == 0:
        return time, altitude, velocity
    time_end = time[-1]
    altitude_end = altitude[-1]
    velocity_end = velocity[-1]
    downsampling_factor = int(np.round(timestep/delt))
    time = time[::downsampling_factor]
    altitude = altitude[::downsampling_factor]
    velocity = velocity[::downsampling_factor]
    if time[-1] != time_end: # If last point(s) are removed by downsampling.
        time = np.append(time, time_end)
        altitude = np.append(altitude, altitude_end)
        velocity = np.append(velocity, velocity_end)

    return time, altitude, velocity


if __name__ == '__main__':
    import argparse
    from matplotlib import pyplot as plt
    parser = argparse.ArgumentParser('Parachute descent computation')
    parser.add_argument('parachute', help='Parachute type')
    parser.add_argument('weight', type=float, help='Payload weight in kg')
    parser.add_argument('-p', '--parameters', required=False, default='parachute_parameters.tsv', help='Parachute parameter file')
    parser.add_argument('-a', '--altitude', required=False, type=float, default=30000., help='Start altitude')
    parser.add_argument('-v', '--velocity', required=False, type=float, default=0., help='Start velocity')
    parser.add_argument('--area', required=False, type=float, default=0.15, help='Payload area')
    args = parser.parse_args()
    parachute_parameter_list = readParachuteParameterList(args.parameters)
    parachute_parameters = lookupParachuteParameters(parachute_parameter_list, args.parachute)
    timestep = 10
    time, altitude, velocity = parachuteDescent(args.altitude, timestep, args.weight, parachute_parameters, args.area, initial_velocity=-args.velocity)
    plt.plot(-velocity, altitude/1000.)
    plt.xlabel('Descent velocity (m/s)')
    plt.ylabel('Altitude (km)')
    plt.show()
