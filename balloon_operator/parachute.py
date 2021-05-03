#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute descent on parachute.

The computation is based on Jens Söder's BalloonTrajectory MATLAB program.

Created on Mon Apr 19 18:14:53 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
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


def parachuteDescent(alt_start, timestep, payload_weight, parachute_parameters, payload_area, payload_drag_coefficient=0.25):
    """
    Compute descent on parachute by solving the equation of motion.

    This is a port of the descent function in Jens Söder's BalloonTrajectory
    MATLAB program.
    """

    # Initialise variables.
    t = 0
    z = alt_start;
    s = 0
    
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
    downsampling_factor = int(np.round(timestep/delt))
    time = time[::downsampling_factor]
    altitude = altitude[::downsampling_factor]
    velocity = velocity[::downsampling_factor]

    return time, altitude, velocity
