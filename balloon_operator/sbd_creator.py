#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a binary sbd file in format of SparkFun Artemis Global Tracker.

Created on Mon May 24 13:52:19 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
import datetime
import argparse
from balloon_operator import sbd_receiver

def main(position, time=None, output_file=None):
    """
    Main: Write binary SBD message corresponding to given data to file.
    """
    data = {'LON': position[0],
            'LAT': position[1],
            'ALT': position[2],
            'DATETIME': datetime.datetime.utcnow() if time is None else time}
    message = sbd_receiver.encodeSdb(data)
    if output_file:
        with open(output_file, 'wb') as fd:
            fd.write(message)
    else:
        print(message)
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--position', required=False, default=None, help='Position lon,lat,alt')
    parser.add_argument('-t', '--time', required=False, default=None, help='Time in ISO format YYYY-mm-dd HH:MM:SS')
    parser.add_argument('-o', '--output', required=False, default=None, help='Output file')
    args = parser.parse_args()
    if args.position is not None:
        position = np.array(args.position.split(',')).astype(float)
    else:
        position = None
    if args.time is not None:
        time = datetime.datetime.fromisoformat(args.time)
    else:
        time = None
    main(position, time=time, output_file=args.output)
