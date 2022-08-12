#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android front-end to translate messages.

Copyright (C) 2022 Andreas Schneider <andreas.schneider@fmi.fi>

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

import termuxgui as tg
import sys
import argparse
from balloon_operator import comm


def displayMessage(msg, tv_datetime, tv_lat, tv_lon, tv_alt, tv_press, tv_temp, tv_batt):
    """
    Display a message in the GUI.
    """
    tv_datetime.settext('Time: {}'.format(
            msg['DATETIME'].isoformat() if 'DATETIME' in msg else '??'))
    tv_lat.settext('Latitude: '+\
                   ('{:.6f}°'.format(msg['LAT']) if 'LAT' in msg else '??'))
    tv_lon.settext('Longitude: '+\
                   ('{:.6f}°'.format(msg['LON']) if 'LON' in msg else '??'))
    tv_alt.settext('Altitude: '+\
                   ('{:.2f} m'.format(msg['ALT']) if 'ALT' in msg else '??'))
    tv_press.settext('Pressure: '+\
                     ('{:.1f} hPa'.format(msg['PRESS']) if 'PRESS' in msg else '??'))
    tv_temp.settext('Temperature: '+\
                    ('{:.1f}°C'.format(msg['TEMP']) if 'TEMP' in msg else '??'))
    tv_batt.settext('Battery: '+\
                    ('{:.2f} V'.format(msg['BATTV']) if 'BATTV' in msg else '??'))


def main(config_file):
    """
    Main function.
    """
    settings = comm.readCommSettings(config_file)
    message_handler = comm.messageHandlerFromSettings(settings)
    message_handler.connect()

    with tg.Connection() as c:
        a = tg.Activity(c)
        layout = tg.LinearLayout(a)
        tv_datetime = tg.TextView(a, 'Time:', layout)
        tv_lat = tg.TextView(a, 'Latitude:', layout)
        tv_lon = tg.TextView(a, 'Longitude:', layout)
        tv_alt = tg.TextView(a, 'Altitude:', layout)
        tv_press = tg.TextView(a, 'Pressure:', layout)
        tv_temp = tg.TextView(a, 'Temperature:', layout)
        tv_batt = tg.TextView(a, 'Battery:', layout)
        bt_retr = tg.Button(a, 'Retrieve', layout)

        for ev in c.events(): # waits for events from the gui
            if ev.type == tg.Event.destroy and ev.value['finishing']:
                message_handler.disconnect()
                a.finish()
                sys.exit()
            if ev.type == tg.Event.click and ev.value['id'] == bt_retr:
                messages = message_handler.getDecodedMessages()
                if len(messages) > 0:
                    msg = messages[-1]
                    displayMessage(msg, tv_datetime, tv_lat, tv_lon, tv_alt, tv_press, tv_temp, tv_batt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Message translator for Android')
    parser.add_argument('config', help='configuration file')
    args = parser.parse_args()
    main(args.config)
