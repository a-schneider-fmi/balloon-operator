#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse and display payload-specific message entries for WIFVOS (Water vapour Isotopologue Flask sampling for the Validation Of Satellite data).

Created on Mon Sep  6 17:50:22 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

from PySide6.QtWidgets import QWidget, QLabel
import numpy as np

def parseUserval1(userval1):
    """
    Parse cutter, heating, pump and event status from USERVAL1 field.
    """
    cutter1_status = (userval1 & 1) == 1
    cutter2_status = (userval1 & 2) == 2
    heating_status = (userval1 & 4) == 4
    pump_status = (userval1 & 8) == 8
    event_status = (userval1 & 16) == 16
    return cutter1_status, cutter2_status, heating_status, pump_status, event_status

def parseUserval5(userval5):
    """
    Parse valve status from USERVAL5 field.
    """
    valve_states = [np.uint16(userval5 & 0xffff), np.uint16(userval5 >> 16)]
    valve_text = ['', '']
    for manifold in range(2):
        for valve in range(12):
            if len(valve_text[manifold]) > 0:
                valve_text[manifold] += ' '
            valve_text[manifold] += 'o' if valve_states[manifold] & (1 << valve) else '-'
    return valve_text

def statusText(status):
    return 'on' if status else 'off'

def cutterText(status):
    return 'fired' if status else 'not fired'

def setPayloadData(payload_widget, data):
    """
    Set data for WIFVOS payload widget.

    @param payload_widget widget instance from QUiLoader
    @param data message data
    """
    widget_press =  payload_widget.findChild(QLabel, 'label_manifold_pressure_value')
    if 'USERVAL3' in data:
        widget_press.setText('{} Pa'.format(data['USERVAL3']))
    else:
        widget_press.setText('?? Pa')
    widget_flowrate =  payload_widget.findChild(QLabel, 'label_flowrate_value')
    if 'USERVAL4' in data:
        widget_flowrate.setText('{} sccm'.format(data['USERVAL4']))
    else:
        widget_flowrate.setText('?? sccm')
    widget_inlet = payload_widget.findChild(QLabel, 'label_inlet_status')
    widget_outlet = payload_widget.findChild(QLabel, 'label_outlet_status')
    widget_pump = payload_widget.findChild(QLabel, 'label_pump_status')
    widget_heating_temperature = payload_widget.findChild(QLabel, 'label_heating_temperature_value')
    widget_event = payload_widget.findChild(QLabel, 'label_event_value')
    if 'USERVAL5' in data:
        valve_text = parseUserval5(data['USERVAL5'])
        widget_inlet.setText(valve_text[0])
        widget_outlet.setText(valve_text[1])
    else:
        widget_inlet.setText('??')
        widget_outlet.setText('??')
    if 'USERVAL1' in data:
        cutter1_status, cutter2_status, heating_status, pump_status, event_status = parseUserval1(data['USERVAL1'])
        widget_pump.setText(statusText(pump_status))
        widget_event.setText('yes' if event_status else 'no')
    else:
        widget_pump.setText('??')
        widget_event.setText('??')
    if 'USERVAL2' in data:
        widget_heating_temperature.setText('{} °C'.format(data['USERVAL2']))
    else:
        widget_heating_temperature.setText('?? °C')

if __name__ == '__main__':
    """
    Script main for testing purposes.
    """
    import argparse
    from balloon_operator import message_sbd
    parser = argparse.ArgumentParser('WIFVOS payload message parser')
    parser.add_argument('-m', '--message', required=False, default=None, help='Translate binary message given as hex string')
    args = parser.parse_args()
    if args.message:
        message_handler = message_sbd.MessageSbd()
        data = message_handler.decodeMessage(message_sbd.MessageSbd.asc2bin(args.message))
        print(data)
        if 'USERVAL1' in data:
            cutter1_status, cutter2_status, heating_status, pump_status, event_status = parseUserval1(data['USERVAL1'])
            print('Cutters: {}, {}'.format(cutterText(cutter1_status), cutterText(cutter2_status)))
            print('Heating: {}'.format(statusText(heating_status)))
            print('Pump: {}'.format(statusText(pump_status)))
            print('Is {} event message.'.format('an' if event_status else 'no'))
        if 'USERVAL5' in data:
            valve_text = parseUserval5(data['USERVAL5'])
            print('Inlet:  {}'.format(valve_text[0]))
            print('Outlet: {}'.format(valve_text[1]))
        if 'USERVAL2' in data:
            print('Battery temperature: {} °C'.format(data['USERVAL2']))
