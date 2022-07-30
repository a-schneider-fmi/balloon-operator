#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graphical user interface for Balloon Operator.

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

import sys
from PySide6.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox
from PySide6.QtCore import Slot, Signal, QObject, QRunnable, QThreadPool, QTimer, QFile
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtUiTools import QUiLoader
from gui_mainwidget import Ui_MainWidget
from gui_operatorwidget import Ui_OperatorWidget
import gui_icons
from balloon_operator import filling, parachute, trajectory_predictor, download_model_data, message, message_sbd, utils
import configparser
import datetime
import argparse
import tempfile
import numpy as np
import os.path
import traceback
import logging
import gpxpy
import gpxpy.gpx
import geog
from copy import deepcopy
import glob
import importlib.util
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


""" Worker thread classes =====================================================
    Source: https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
"""
class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:
    finished: No data
    error: tuple (exctype, value, traceback.format_exc() )
    result: object data returned from processing, anything
    progress: int indicating % progress
    '''
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    @param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    @type callback: function
    @param args: Arguments to pass to the callback function
    @param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


""" MainWidget ================================================================
"""
class MainWidget(QWidget):
    def __init__(self):
        super(MainWidget, self).__init__()
        self.ui = Ui_MainWidget()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(QPixmap(":/icons/icon.png")))
        self.operator_widget = OperatorWidget()
        self.operator_widget.stopLiveOperation.connect(self.onStopLiveOperation)

        self.ui.dt_launch_datetime.setDateTime(utils.roundSeconds(datetime.datetime.utcnow()))
        for fill_gas in filling.FillGas:
            self.ui.combo_fill_gas.addItem(filling.fill_gas_names[fill_gas], fill_gas)
        self.ui.edit_output_file.setText(os.path.join(tempfile.gettempdir(), 'trajectory.gpx'))
        self.ui.edit_webpage_file.setText(os.path.join(tempfile.gettempdir(), 'trajectory.html'))
        self.ui.edit_map_file.setText(os.path.join(tempfile.gettempdir(), 'trajectory.png'))
        self.ui.edit_tsv_file.setText(os.path.join(tempfile.gettempdir(), 'trajectory.tsv'))
        self.balloon_parameter_list = np.zeros((3,0), dtype=[('weight', 'f8'), ('burst_diameter', 'f8'), ('drag_coefficient', 'f8')])
        self.balloon_parameter_file = None
        self.parachute_parameter_list = np.zeros((3,0), dtype=[('name', 'U25'), ('diameter', 'f8'), ('drag_coefficient', 'f8')])
        self.parachute_parameter_file = None
        self.balloon_performance = {}
        self.timestep = 10
        self.model_path = tempfile.gettempdir()
        self.setBalloonPicture(self.ui.check_descent_balloon.isChecked())
        for model_name in trajectory_predictor.readModelData.keys():
            self.ui.combo_model.addItem(model_name)

        self.ui.button_now.clicked.connect(self.launchtimeNow)
        self.ui.button_load_payload.clicked.connect(self.onLoadPayload)
        self.ui.button_save_payload.clicked.connect(self.onSavePayload)
        self.ui.check_descent_balloon.stateChanged.connect(self.onChangeCheckDescentBalloon)
        self.ui.check_cut.stateChanged.connect(self.onChangeCheckCut)
        self.ui.spin_payload_weight.valueChanged.connect(self.onChangeBalloonParameter)
        self.ui.combo_asc_balloon.activated.connect(self.onChangeBalloonParameter)
        self.ui.combo_desc_balloon.activated.connect(self.onChangeBalloonParameter)
        self.ui.combo_fill_gas.activated.connect(self.onChangeBalloonParameter)
        self.ui.spin_asc_velocity.valueChanged.connect(self.onChangeBalloonParameter)
        self.ui.spin_desc_velocity.valueChanged.connect(self.onChangeBalloonParameter)
        self.ui.spin_cut_altitude.valueChanged.connect(self.onChangeCutAltitude)
        self.ui.combo_cut_altitude_unit.activated.connect(self.onChangeCutAltitude)
        self.ui.button_output_file_dialog.clicked.connect(self.onOutputFileSelector)
        self.ui.check_webpage.stateChanged.connect(self.onChangeCheckWebpage)
        self.ui.button_webpage_file_dialog.clicked.connect(self.onWebpageFileSelector)
        self.ui.check_map.stateChanged.connect(self.onChangeCheckMap)
        self.ui.button_map_file_dialog.clicked.connect(self.onMapFileSelector)
        self.ui.check_tsv.stateChanged.connect(self.onChangeCheckTsv)
        self.ui.button_tsv_file_dialog.clicked.connect(self.onTsvFileSelector)
        self.ui.button_forecast.clicked.connect(self.onForecast)
        self.ui.button_live_operation.clicked.connect(self.onLiveOperation)

        self.threadpool = QThreadPool()
        logging.info('Multithreading with maximum {} threads'.format(self.threadpool.maxThreadCount()))

    def loadBalloonParameters(self, filename):
        """
        Load balloon parameter data into the combo boxes.
        """
        self.balloon_parameter_file = filename
        self.balloon_parameter_list = filling.readBalloonParameterList(filename)
        self.ui.combo_asc_balloon.clear()
        self.ui.combo_desc_balloon.clear()
        for ind in range(len(self.balloon_parameter_list['weight'])):
            weight = self.balloon_parameter_list['weight'][ind]
            self.ui.combo_asc_balloon.addItem('{:.0f}'.format(weight), weight)
            self.ui.combo_desc_balloon.addItem('{:.0f}'.format(weight), weight)

    def loadParachuteParameters(self, filename):
        """
        Load parachute parameters into the combo box.
        """
        self.parachute_parameter_file = filename
        self.parachute_parameter_list = parachute.readParachuteParameterList(filename)
        self.ui.combo_parachute.clear()
        for ind in range(len(self.parachute_parameter_list['name'])):
            self.ui.combo_parachute.addItem(self.parachute_parameter_list['name'][ind])

    def loadPayloadIni(self, config_file):
        """
        Load values from a payload ini file into the GUI.
        """
        config = configparser.ConfigParser()
        config.read(config_file)
        self.blockSignals(True)
        try:
            self.loadBalloonParameters(config['parameters'].get('balloon', fallback='totex_balloon_parameters.tsv'))
            self.loadParachuteParameters(config['parameters'].get('parachute', fallback='parachute_parameters.tsv'))
            self.ui.spin_launch_longitude.setValue(config['launch_site'].getfloat('longitude'))
            self.ui.spin_launch_latitude.setValue(config['launch_site'].getfloat('latitude'))
            self.ui.spin_launch_altitude.setValue(config['launch_site'].getfloat('altitude'))
            self.ui.spin_payload_weight.setValue(config['payload'].getfloat('payload_weight'))
            self.ui.spin_payload_area.setValue(config['payload'].getfloat('payload_area'))
            if 'ascent_balloon_weight' in config['payload']:
                self.ui.combo_asc_balloon.setCurrentText(config['payload'].get('ascent_balloon_weight'))
            else:
                self.ui.combo_asc_balloon.setCurrentText(config['payload'].get('balloon_weight'))
            if 'descent_balloon_weight' in config['payload'] and 'ascent_velocity' in config['payload']:
                self.ui.combo_desc_balloon.setEnabled(True)
                self.ui.combo_desc_balloon.setCurrentText(config['payload'].get('descent_balloon_weight'))
                self.ui.check_descent_balloon.setChecked(True)
                self.ui.spin_desc_velocity.setEnabled(True)
            else:
                self.ui.combo_desc_balloon.setEnabled(False)
                self.ui.check_descent_balloon.setChecked(False)
                self.ui.spin_desc_velocity.setEnabled(False)
            self.ui.combo_fill_gas.setCurrentText(config['payload']['fill_gas'])
            self.ui.combo_parachute.setCurrentText(config['payload']['parachute_type'])
            self.ui.spin_asc_velocity.setValue(config['payload'].getfloat('ascent_velocity'))
            self.ui.spin_desc_velocity.setValue(config['payload'].getfloat('descent_velocity', fallback=0.))
            if 'cut_altitude' in config['payload']:
                self.ui.spin_cut_altitude.setValue(config['payload'].getfloat('cut_altitude', fallback=0.))
                self.ui.check_cut.setChecked(True)
                self.ui.spin_cut_altitude.setEnabled(True)
                self.ui.combo_cut_altitude_unit.setCurrentIndex(0)
            elif 'cut_pressure' in config['payload']:
                self.ui.spin_cut_altitude.setValue(config['payload'].getfloat('cut_pressure', fallback=0.))
                self.ui.check_cut.setChecked(True)
                self.ui.spin_cut_altitude.setEnabled(True)
                self.ui.combo_cut_altitude_unit.setCurrentIndex(1)
            else:
                self.ui.spin_cut_altitude.setEnabled(False)
                self.ui.spin_cut_altitude.setValue(0.)
        except KeyError:
            QMessageBox.warning(self, 'Loading payload data', 'The file misses essential information.')
        self.blockSignals(False)
        self.computeBalloonPerformance()
        if 'parameters' in config:
            self.timestep = config['parameters'].getint('timestep', fallback=10)
            self.model_path = config['parameters'].get('model_path', fallback=tempfile.gettempdir())

    def savePayloadIni(self, config_file):
        """
        Save payload information in the GUI to a payload ini file.
        """
        config = configparser.ConfigParser()
        config['launch_site'] = {
                'longitude': self.ui.spin_launch_longitude.value(),
                'latitude': self.ui.spin_launch_latitude.value(),
                'altitude': self.ui.spin_launch_altitude.value()}
        config['payload'] = {
                'payload_weight': self.ui.spin_payload_weight.value(),
                'payload_area': self.ui.spin_payload_area.value(),
                'ascent_balloon_weight': self.ui.combo_asc_balloon.currentData(),
                'fill_gas': self.ui.combo_fill_gas.currentText(),
                'parachute_type': self.ui.combo_parachute.currentText(),
                'ascent_velocity': self.ui.spin_asc_velocity.value()}
        if self.ui.check_descent_balloon.isChecked():
            config['payload']['descent_balloon_weight'] = str(self.ui.combo_desc_balloon.currentText())
            config['payload']['descent_velocity'] = str(self.ui.spin_desc_velocity.value())
        config['parameters'] = {
                'balloon': self.balloon_parameter_file,
                'parachute': self.parachute_parameter_file}
        with open(config_file, 'w') as fd:
            config.write(fd)

    def launchtimeNow(self):
        """
        Set launch datetime to now.
        """
        self.ui.dt_launch_datetime.setDateTime(utils.roundSeconds(datetime.datetime.utcnow()))

    def computeBalloonPerformance(self):
        """
        Compute balloon performance and update display.
        """
        payload_weight = self.ui.spin_payload_weight.value()
        fill_gas = self.ui.combo_fill_gas.currentData()
        ascent_balloon_parameters = filling.lookupParameters(self.balloon_parameter_list, self.ui.combo_asc_balloon.currentData())
        ascent_velocity = self.ui.spin_asc_velocity.value()
        if self.ui.check_descent_balloon.isChecked():
            descent_balloon_parameters = filling.lookupParameters(self.balloon_parameter_list, self.ui.combo_desc_balloon.currentData())
            descent_velocity = self.ui.spin_desc_velocity.value()
            ascent_launch_radius, descent_launch_radius, ascent_neutral_lift, descent_neutral_lift, \
            ascent_burst_height, descent_burst_height = filling.twoBalloonFilling(
                ascent_balloon_parameters, descent_balloon_parameters, payload_weight, 
                ascent_velocity, descent_velocity, fill_gas=fill_gas)
            descent_fill_volume = 4./3.*np.pi*descent_launch_radius**3
            self.ui.label_desc_fill_volume_value.setText('{:.3f} m3'.format(descent_fill_volume))
            self.ui.label_desc_lift_value.setText('{:.3f} kg'.format(descent_neutral_lift))
            self.ui.label_desc_burst_height_value.setText('{:.0f} m'.format(descent_burst_height))
        else:
            ascent_launch_radius, ascent_neutral_lift, ascent_burst_height = filling.balloonFilling(
                    ascent_balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas)
            descent_balloon_parameters = None
            descent_velocity = None
            descent_launch_radius = None
            descent_burst_height = None
            self.ui.label_desc_fill_volume_value.setText('--')
            self.ui.label_desc_lift_value.setText('--')
            self.ui.label_desc_burst_height_value.setText('--')
        ascent_fill_volume = 4./3.*np.pi*ascent_launch_radius**3
        self.ui.label_asc_fill_volume_value.setText('{:.3f} m3'.format(ascent_fill_volume))
        self.ui.label_asc_lift_value.setText('{:.3f} kg'.format(ascent_neutral_lift))
        self.ui.label_asc_burst_height_value.setText('{:.0f} m'.format(ascent_burst_height))
        self.balloon_performance = {
                'payload_weight': payload_weight,
                'ascent_velocity': ascent_velocity,
                'ascent_launch_radius': ascent_launch_radius,
                'ascent_burst_height': ascent_burst_height,
                'descent_velocity': descent_velocity,
                'descent_launch_radius': descent_launch_radius,
                'descent_burst_height': descent_burst_height}

    def setWarningText(self):
        ascent_burst_height = self.balloon_performance['ascent_burst_height']
        descent_burst_height = self.balloon_performance['descent_burst_height']
        cut_altitude = self.getCutAltitude()
        if cut_altitude is not None:
            if ascent_burst_height < cut_altitude + 1000.:
                self.ui.label_balloon_performance_warning.setText(
                        'Ascent balloon bursts too early.')
            elif descent_burst_height is not None and descent_burst_height < cut_altitude + 1000.:
                self.ui.label_balloon_performance_warning.setText(
                        'Descent balloon bursts too early.')
            elif descent_burst_height is not None and descent_burst_height - ascent_burst_height < 1000.:
                self.ui.label_balloon_performance_warning.setText(
                        'Descent balloon bursts before ascent balloon.')
            else:
                self.ui.label_balloon_performance_warning.setText('')
        else:
            if descent_burst_height is not None:
                self.ui.label_balloon_performance_warning.setText(
                        'Cutter recommended for two-balloon flight.')
            else:
                self.ui.label_balloon_performance_warning.setText('')
        if descent_burst_height is not None and self.balloon_performance['descent_velocity'] <= 0:
            self.ui.label_balloon_performance_warning.setText(
                    'Descent velocity must be positive.')
        if self.balloon_performance['ascent_velocity'] <= 0:
            self.ui.label_balloon_performance_warning.setText(
                    'Ascent velocity must be positive.')

    def setBalloonPicture(self, has_descent_balloon):
        """
        Load drawing of balloon configuration.
        """
        if has_descent_balloon:
            filename = 'gui_drawing_two_balloons.svg'
        else:
            filename = 'gui_drawing_one_balloon.svg'
        self.ui.widget_drawing.load(os.path.join(os.path.dirname(__file__),filename))

    def setLanding(self, time, longitude, latitude, altitude, flight_range, border_crossing):
        """
        Set result section of UI.
        """
        self.ui.label_landing_time_value.setText(
                '--' if altitude is None else '{}'.format(utils.roundSeconds(time)))
        self.ui.label_landing_longitude_value.setText(
                '--' if longitude is None else '{:.5f}°'.format(longitude))
        self.ui.label_landing_latitude_value.setText(
                '--' if latitude is None else '{:.5f}°'.format(latitude))
        self.ui.label_landing_altitude_value.setText(
                '--' if altitude is None else '{:.0f} m'.format(altitude))
        self.ui.label_range_value.setText(
                '--' if flight_range is None else '{:.0f} km'.format(flight_range))
        self.ui.label_border_crossing_value.setText(
                '??' if border_crossing is None else '{}'.format(border_crossing))

    def getCutAltitude(self):
        """
        Return selected cut altitude, or None if no cutting is selected.
        """
        if self.ui.check_cut.isChecked():
            if self.ui.combo_cut_altitude_unit.currentText() == 'hPa':
                return utils.press2alt(self.ui.spin_cut_altitude.value()*100., p0=101325.) # TODO: use real sea-level pressure, or take altitude from model data
            else:
                return self.ui.spin_cut_altitude.value()
        else:
            return None

    def flightParameters(self):
        """
        Get parameters for flight.
        """
        parameters = {
                'parachute_parameters': parachute.lookupParachuteParameters(self.parachute_parameter_list, self.ui.combo_parachute.currentText()),
                'payload_area': self.ui.spin_payload_area.value(),
                'launch_lon': self.ui.spin_launch_longitude.value(),
                'launch_lat': self.ui.spin_launch_latitude.value(),
                'launch_alt': self.ui.spin_launch_altitude.value(),
                'launch_datetime': self.ui.dt_launch_datetime.dateTime().toPython(),
                'model': self.ui.combo_model.currentText(),
                'output_file': self.ui.edit_output_file.text(),
                'webpage_file': self.ui.edit_webpage_file.text() if self.ui.check_webpage.isChecked() else None,
                'map_file': self.ui.edit_map_file.text() if self.ui.check_map.isChecked() else None,
                'tsv_file': self.ui.edit_tsv_file.text() if self.ui.check_tsv.isChecked() else None
                }
        cut_altitude = self.getCutAltitude()
        if cut_altitude is not None:
            parameters['top_altitude'] = np.minimum(cut_altitude, self.balloon_performance['ascent_burst_height'])
        else:
            if 'ascent_burst_height' in self.balloon_performance:
                parameters['top_altitude'] = self.balloon_performance['ascent_burst_height']
            else:
                parameters['top_altitude'] = 0.
        parameters.update(self.balloon_performance)
        return parameters

    def doForecast(self, parameters, progress_callback=None, error_callback=None):
        """
        Compute a trajectory forecast.
        Function is typically executed in a separate thread.
        """
        # Download and read in model data.
        model_filenames = download_model_data.getModelData(
                parameters['model'],
                parameters['launch_lon'], parameters['launch_lat'],
                parameters['launch_datetime'], self.model_path)
        if model_filenames is None or (isinstance(model_filenames,list) and (model_filenames) == 0):
            if callable(error_callback):
                error_callback('Error retrieving model data.')
            return None
        model_data = trajectory_predictor.readModelData[parameters['model']](model_filenames)
    
        # Do prediction.
        track, waypoints, flight_range = trajectory_predictor.predictBalloonFlight(
            parameters['launch_datetime'], parameters['launch_lon'],
            parameters['launch_lat'], parameters['launch_alt'],
            parameters['payload_weight'], parameters['payload_area'],
            parameters['ascent_velocity'],
            parameters['top_altitude'],
            parameters['parachute_parameters'],
            model_data, self.timestep, 
            descent_velocity=parameters['descent_velocity'])
        if self.ui.check_border_crossing.isChecked():
            try:
                is_abroad, foreign_countries = trajectory_predictor.checkBorderCrossing(track)
                if is_abroad.any():
                    border_crossing = 'crossed into {}'.format(', '.join(foreign_countries))
                else:
                    border_crossing = 'domestic'
            except Exception as err:
                print('Error determining border crossing: {}'.format(err))
                border_crossing = None
                is_abroad = None
                foreign_countries = None
        else:
            is_abroad = False
            foreign_countries = None
            border_crossing = None
        self.setLanding(track.segments[-1].points[-1].time, track.segments[-1].points[-1].longitude, track.segments[-1].points[-1].latitude, track.segments[-1].points[-1].elevation, flight_range, border_crossing)

        # Save resulting trajectory.
        output_file = parameters['output_file']
        output_ext = os.path.splitext(output_file)[1]
        if output_ext.lower() == '.kml':
            trajectory_predictor.writeKml(track, output_file, waypoints=waypoints)
        else:
            trajectory_predictor.writeGpx(track, output_file, waypoints=waypoints, description=track.description)
        if parameters['webpage_file']:
            trajectory_predictor.createWebpage(track, waypoints, parameters['webpage_file'])
        if parameters['map_file']:
            trajectory_predictor.exportImage(track, parameters['map_file'], waypoints=waypoints)
        if parameters['tsv_file']:
            trajectory_predictor.exportTsv(
                    track, parameters['tsv_file'], top_height=parameters['top_altitude'],
                    is_abroad=is_abroad, foreign_countries=foreign_countries)
        return {'lon': track.segments[-1].points[-1].longitude,
                'lat': track.segments[-1].points[-1].latitude,
                'alt': track.segments[-1].points[-1].elevation,
                'range': flight_range,
                'top_alt': parameters['top_altitude']}

    def doHourlyForecast(self, parameters, hours, progress_callback=None, error_callback=None):
        """
        Compute an hourly forecast.
        Function is typically executed in a separate thread.
        """
        hourly_track, _, _ = trajectory_predictor.hourlyForecast(
            parameters['launch_datetime'], parameters['launch_lon'],
            parameters['launch_lat'], parameters['launch_alt'],
            parameters['payload_weight'], parameters['payload_area'],
            parameters['ascent_velocity'],
            parameters['top_altitude'],
            parameters['parachute_parameters'],
            hours,
            self.timestep, parameters['model'], self.model_path, parameters['output_file'],
            descent_velocity=parameters['descent_velocity'])
        if hourly_track is None and callable(error_callback):
            error_callback('Necessary data could not be downloaded.')

    @Slot()
    def onLoadPayload(self):
        """
        Callback when clicking the load payload button.
        """
        filename, filetype = QFileDialog.getOpenFileName(self, 'Open payload information', None, 'Configuration files (*.ini);;All files (*)')
        if filename:
            self.loadPayloadIni(filename)

    @Slot()
    def onSavePayload(self):
        """
        Callback when clicking the save payload button.
        """
        filename, filetype = QFileDialog.getSaveFileName(self, 'Save payload information', None, 'Configuration files (*.ini);;All files (*)')
        if filename:
            if os.path.splitext(filename)[1].lower() != '.ini':
                filename += '.ini'
            self.savePayloadIni(filename)

    @Slot()
    def onChangeCheckDescentBalloon(self, new_state):
        """
        Callback when the checkbox to use a descent balloon is changed.
        """
        self.ui.combo_desc_balloon.setEnabled(new_state)
        self.ui.spin_desc_velocity.setEnabled(new_state)
        self.setBalloonPicture(new_state)
        self.computeBalloonPerformance()
        self.setWarningText()

    @Slot()
    def onChangeCheckCut(self, new_state):
        """
        Callback when the checkbox to use a cutter is changed.
        """
        self.ui.spin_cut_altitude.setEnabled(new_state)
        self.ui.combo_cut_altitude_unit.setEnabled(new_state)
        self.setWarningText()

    @Slot()
    def onChangeBalloonParameter(self, value):
        """
        Callback when a balloon parameter is changed.
        """
        self.computeBalloonPerformance()
        self.setWarningText()

    @Slot()
    def onChangeCutAltitude(self, value):
        """
        Callback when cut altitude is changed.
        """
        self.setWarningText()

    @Slot()
    def onOutputFileSelector(self):
        """
        Callback when the button to select an output file is clicked.
        """
        output_file, filetype = QFileDialog.getSaveFileName(self, 'Save trajectory', os.path.dirname(self.ui.edit_output_file.text()), 'GPX tracks (*.gpx);;KML tracks (*.kml)')
        if output_file:
            if filetype == 'GPX tracks (*.gpx)' and os.path.splitext(output_file)[1].lower() != '.gpx':
                output_file += '.gpx'
            if filetype == 'KML tracks (*.kml)' and os.path.splitext(output_file)[1].lower() != '.kml':
                output_file += '.kml'
            self.ui.edit_output_file.setText(output_file)

    @Slot()
    def onChangeCheckWebpage(self, state):
        """
        Callback when checkbox whether to create a webpage is changed.
        """
        self.ui.edit_webpage_file.setEnabled(state)
        self.ui.button_webpage_file_dialog.setEnabled(state)

    @Slot()
    def onWebpageFileSelector(self):
        """
        Callback when the button to select a webpage file name is clicked.
        """
        webpage_file, filetype = QFileDialog.getSaveFileName(self, 'Save webpage', os.path.dirname(self.ui.edit_webpage_file.text()), 'Webpages (*.html)')
        if webpage_file:
            fileext = os.path.splitext(webpage_file)[1].lower()
            if fileext != '.html' and fileext != '.htm':
                webpage_file += '.html'
            self.ui.edit_webpage_file.setText(webpage_file)

    @Slot()
    def onChangeCheckMap(self, state):
        """
        Callback when checkbox whether to create a map is changed.
        """
        self.ui.edit_map_file.setEnabled(state)
        self.ui.button_map_file_dialog.setEnabled(state)

    @Slot()
    def onMapFileSelector(self):
        """
        Callback when the button to select a map file name is clicked.
        """
        filename, filetype = QFileDialog.getSaveFileName(self, 'Save map image', os.path.dirname(self.ui.edit_map_file.text()), 'Images (*.png)')
        if filename:
            fileext = os.path.splitext(filename)[1].lower()
            if fileext != '.png':
                filename += '.png'
            self.ui.edit_map_file.setText(filename)

    @Slot()
    def onChangeCheckTsv(self, state):
        """
        Callback when checkbox whether to create a tsv ACSII output file is changed.
        """
        self.ui.edit_tsv_file.setEnabled(state)
        self.ui.button_tsv_file_dialog.setEnabled(state)

    @Slot()
    def onTsvFileSelector(self):
        """
        Callback when the button to select a tsv output file name is clicked.
        """
        filename, filetype = QFileDialog.getSaveFileName(self, 'Save tsv', os.path.dirname(self.ui.edit_tsv_file.text()), 'Tabular separated values (*.tsv)')
        if filename:
            fileext = os.path.splitext(filename)[1].lower()
            if fileext != '.tsv':
                filename += '.tsv'
            self.ui.edit_tsv_file.setText(filename)

    @Slot()
    def forecastComplete(self):
        """
        Callback executed when the thread to compute a forecast completes.
        """
        self.ui.button_forecast.setEnabled(True)

    @Slot()
    def forecastResult(self, result):
        """
        Callback to handle the result of the thread computing the forecast.
        """
        print(result)

    @Slot()
    def onForecast(self):
        """
        Callback when the button to do a forecast is clicked.
        """
        self.ui.button_forecast.setEnabled(False)

        # Execute calculation in a separate thread in order not to make the GUI unresponsive.
        if self.ui.check_hourly.isChecked():
            worker = Worker(
                    self.doHourlyForecast,
                    self.flightParameters(),
                    self.ui.spin_hourly.value(),
                    error_callback=self.showError)
        else:
            worker = Worker(
                    self.doForecast,
                    self.flightParameters(),
                    error_callback=self.showError)
        worker.signals.result.connect(self.forecastResult)
        worker.signals.finished.connect(self.forecastComplete)
        self.threadpool.start(worker)

    @Slot()
    def onLiveOperation(self):
        """
        Callback when the button to do live operation is clicked.
        """
        if not self.balloon_performance:
            QMessageBox.critical(self, 'Live operation', 'Flight data not set. Please make the respective settings first.')
            return
        self.ui.button_live_operation.setEnabled(False)
        self.operator_widget.startLiveForecast(self.flightParameters(), self.model_path, self.timestep)

    @Slot()
    def onStopLiveOperation(self):
        """
        Callback when the live operation stops (e.g. the live operation window is closed)
        """
        self.ui.button_live_operation.setEnabled(True)

    @Slot()
    def showError(self, message):
        """
        Callback to be executed when a thread produces an error.
        """
        QMessageBox.critical(self, 'Balloon operator', message)


""" OperatorWidget ============================================================
"""
class OperatorWidget(QWidget):
    def __init__(self):
        super(OperatorWidget, self).__init__()
        self.ui = Ui_OperatorWidget()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(QPixmap(":/icons/icon.png")))
        self.ui.button_load_config.clicked.connect(self.onLoadConfig)
        self.ui.spin_query_time.valueChanged.connect(self.onChangeQueryTime)
        self.ui.button_query_now.clicked.connect(self.onQueryNow)
        self.ui.button_send.clicked.connect(self.onSendIridium)
        self.ui.combo_payload_type.currentIndexChanged.connect(self.onComboPayloadChanged)
        self.flight_parameters = {}
        self.timestep = 10
        self.model_path = tempfile.gettempdir()
        self.model_data = None
        self.comm_settings = None
        self.message_handler = None
        self.timer = QTimer(self)
        self.timer.setInterval(60000) # default time of 1 minute
        self.timer.timeout.connect(self.queryMessages)
        self.threadpool = QThreadPool()

        # Set up plots.
        self.ui.layout_plots.addWidget(NavigationToolbar(self.ui.mpl_canvas, self))
        axes = self.ui.mpl_canvas.figure.subplots(2, sharex=True)
        self.axis_alt = axes[0]
        self.axis_temp = axes[1]
        color = 'tab:red'
        self.axis_alt.set_ylabel('Altitude (km)', color=color)
        self.axis_alt.tick_params(axis="y", colors=color)
        self.line_alt, = self.axis_alt.plot([datetime.datetime.utcnow()], [0], color=color)
        self.axis_alt.set_ylim(0, 30)
        plt.setp(self.axis_alt.get_xticklabels(), visible=False) # make x tick labels invisible
        self.axis_alt.grid(axis='both')
        self.axis_press = self.axis_alt.twinx()
        color = 'tab:blue'
        self.axis_press.set_ylabel('Pressure (hPa)', color=color)
        self.axis_press.tick_params(axis="y", colors=color)
        self.line_press, = self.axis_press.plot([datetime.datetime.utcnow()], [0], color=color)
        self.axis_press.set_ylim(0, 1100)
        self.axis_temp.set_xlabel('Time')
        color = 'tab:red'
        self.axis_temp.set_ylabel('Temperature (°C)', color=color)
        self.axis_temp.tick_params(axis="y", colors=color)
        self.line_temp, = self.axis_temp.plot([datetime.datetime.utcnow()], [0], color=color)
        self.axis_temp.set_ylim(0, 30)
        self.axis_temp.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.axis_temp.grid(axis='both')
        self.axis_battv = self.axis_temp.twinx()
        color = 'tab:blue'
        self.axis_battv.set_ylabel('Battery voltage (V)', color=color)
        self.axis_battv.tick_params(axis="y", colors=color)
        self.line_battv, = self.axis_battv.plot([datetime.datetime.utcnow()], [0], color=color)
        self.axis_battv.set_ylim(0, 4)
        plt.tight_layout()
        self.ui.mpl_canvas.figure.subplots_adjust(hspace=.0) # remove vertical gap between subplots
        self.ui.mpl_canvas.draw()

        # Fill combo box with special payloads.
        self.ui.combo_payload_type.addItem('Generic', None)
        widget_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__),'gui_payloadwidget_*.ui')))
        for widget_file in widget_files:
            name = os.path.splitext(os.path.basename(widget_file))[0][18:].title()
            self.ui.combo_payload_type.addItem(name, widget_file)
        self.ui.combo_payload_type.activated.connect(self.onComboPayloadChanged)
        self.payloadwidget = None

    stopLiveOperation = Signal()

    def closeEvent(self, event):
        """
        Overrides QWidget's closeEvent method.
        """
        self.stopLiveForecast()

    def loadConfig(self, config_file):
        """
        Load a communication configuration file.
        """
        self.comm_settings = trajectory_predictor.readCommSettings(config_file)
        try:
            self.message_handler = trajectory_predictor.messageHandlerFromSettings(self.comm_settings)
        except ValueError as err:
            QMessageBox.critical(self, 'Configuration error', err)
        self.loadIridiumList(config_file)
        if isinstance(self.message_handler,message_sbd.MessageSbd):
            self.ui.label_id.setText('IMEI')
        else:
            self.ui.label_id.setText('Tracker ID')

    def loadIridiumList(self, config_file):
        """
        Load list of IRIDIUM modems from an ini file into the combo boxes.
        """
        config = configparser.ConfigParser()
        config.optionxform = str # Mind case in option names.
        config.read(config_file)
        self.ui.combo_iridium.clear()
        self.ui.combo_receive_imei.clear()
        self.ui.combo_receive_imei.addItem('All', '')
        if 'rockblock_devices' in config.sections():
            for name in config.options('rockblock_devices'):
                imei = config['rockblock_devices'].get(name)
                self.ui.combo_iridium.addItem('{} ({})'.format(name, imei), imei)
                self.ui.combo_receive_imei.addItem('{} ({})'.format(name, imei), str(imei))

    def _cutterStateText(self, state):
        """
        Textual representation of cutter state
        """
        return 'fired' if state else 'not fired'

    def _heatingStateText(self, state):
        """
        Textual representation of heating state
        """
        return 'on' if state else 'off'

    def setStandardData(self, data):
        """
        Sets standard data from a received message.
        """
        self.ui.label_cur_datetime_value.setText(
                '{}'.format(data['DATETIME'].isoformat()) if 'DATETIME' in data
                else '??.??.???? ??:??:??')
        self.ui.label_cur_longitude_value.setText(
                '{:.6f}°'.format(data['LON']) if 'LON' in data
                else '??°')
        self.ui.label_cur_latitude_value.setText(
                '{:.6f}°'.format(data['LAT']) if 'LAT' in data
                else '??°')
        self.ui.label_cur_altitude_value.setText(
                '{:.1f} m'.format(data['ALT']) if 'ALT' in data
                else '?? m')
        self.ui.label_cur_pressure_value.setText(
                '{} hPa'.format(data['PRESS']) if 'PRESS' in data
                else '?? hPa')
        self.ui.label_cur_temperature_value.setText(
                '{:.1f} °C'.format(data['TEMP']) if 'TEMP' in data
                else '?? °C')
        self.ui.label_cur_humidity_value.setText(
                '{:.1f} %'.format(data['HUMID']) if 'HUMID' in data
                else '?? %')
        self.ui.label_cur_battery_value.setText(
                '{:.2f} V'.format(data['BATTV']) if 'BATTV' in data
                else '?? V')
        self.ui.label_cur_cutter1_value.setText(
                self._cutterStateText(data['USERVAL1'] & 1) if 'USERVAL1' in data
                else '??')
        self.ui.label_cur_cutter2_value.setText(
                self._cutterStateText(data['USERVAL1'] & 2) if 'USERVAL1' in data
                else '??')
        self.ui.label_cur_heating_value.setText(
                self._heatingStateText(data['USERVAL1'] & 4) if 'USERVAL1' in data
                else '??')
        self.ui.label_id_value.setText(
                '{}'.format(data['IMEI']) if 'IMEI' in data
                else '??')

    def setAdvancedData(self, data):
        """
        Sets advanced (per-payload) data from a received IRIDIUM message.
        """
        payload_widget_file = self.ui.combo_payload_type.currentData()
        if payload_widget_file is not None:
            try:
                dirname = os.path.dirname(payload_widget_file)
                module_name = os.path.splitext(os.path.basename(payload_widget_file))[0][4:]
                filename = os.path.join(dirname, module_name+'.py')
                print('Loading module: {}'.format(module_name)) # DEBUG
                spec = importlib.util.spec_from_file_location(module_name, filename)
                widget_code = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(widget_code)
            except Exception as err:
                print('Exception while loading payload module {}: {}'.format(module_name, err))
                return
            widget_code.setPayloadData(self.payloadwidget, data)

    def appendTimeseries(self, data):
        """
        Adds standard data from a received IRIDIUM message.
        """
        if 'DATETIME' not in data or data['DATETIME'] is None:
            return
        self.timeseries['DATETIME'].append(data['DATETIME'])
        for key in ['ALT', 'PRESS', 'TEMP', 'BATTV']:
            self.timeseries[key].append(data[key] if key in data else np.nan)

    def plotStandardData(self):
        """
        Updates the plot of the standard data from the tracker.
        """
        self.line_alt.set_data(np.array(self.timeseries['DATETIME']), np.array(self.timeseries['ALT'])/1000.)
        self.axis_alt.set_xlim(np.array(self.timeseries['DATETIME'])[np.array([0,-1])])
        alt_range = np.array([np.nanmin(self.timeseries['ALT'])/1000., np.nanmax(self.timeseries['ALT'])/1000.])
        if np.isfinite(alt_range).all() and alt_range[0] != alt_range[1]:
            self.axis_alt.set_ylim(alt_range)
        self.line_press.set_data(self.timeseries['DATETIME'], self.timeseries['PRESS'])
        press_range = np.array([np.nanmin(self.timeseries['PRESS']), np.nanmax(self.timeseries['PRESS'])])
        if np.isfinite(press_range).all() and press_range[0] != press_range[1]:
            self.axis_press.set_ylim(press_range)
        self.line_temp.set_data(self.timeseries['DATETIME'], self.timeseries['TEMP'])
        temp_range = np.array([np.nanmin(self.timeseries['TEMP']), np.nanmax(self.timeseries['TEMP'])])
        if np.isfinite(temp_range).all() and temp_range[0] != temp_range[1]:
            self.axis_temp.set_ylim(temp_range)
        self.line_battv.set_data(self.timeseries['DATETIME'], self.timeseries['BATTV'])
        battv_range = np.array([np.nanmin(self.timeseries['BATTV']), np.nanmax(self.timeseries['BATTV'])])
        if np.isfinite(battv_range).all() and battv_range[0] != battv_range[1]:
            self.axis_battv.set_ylim(battv_range)
        self.ui.mpl_canvas.draw()

    def setLanding(self, time, longitude, latitude, altitude, flight_range):
        """
        Set landing section of UI.
        """
        self.ui.label_landing_time_value.setText(
                '--' if altitude is None else '{}'.format(utils.roundSeconds(time)))
        self.ui.label_landing_longitude_value.setText(
                '--' if longitude is None else '{:.5f}°'.format(longitude))
        self.ui.label_landing_latitude_value.setText(
                '--' if latitude is None else '{:.5f}°'.format(latitude))
        self.ui.label_landing_altitude_value.setText(
                '--' if altitude is None else '{:.0f} m'.format(altitude))
        self.ui.label_range_value.setText(
                '--' if flight_range is None else '{:.0f} km'.format(flight_range))

    def downloadModelData(self, progress_callback=None, error_callback=None):
        """
        Downloads model data for live forecast.
        """
        self.ui.label_status.setText('Downloading model data.')
        if self.flight_parameters['launch_datetime'] is None:
            self.flight_parameters['launch_datetime'] = datetime.datetime.utcnow()
        filelist = download_model_data.getModelData(
                self.flight_parameters['model'],
                self.flight_parameters['launch_lon'],
                self.flight_parameters['launch_lat'],
                self.flight_parameters['launch_datetime'],
                self.model_path,
                duration=7)
        if filelist is None or (isinstance(filelist,list) and len(filelist) == 0):
            if callable(error_callback):
                error_callback('Error downloading model data.')
            return
        self.model_data = trajectory_predictor.readModelData[self.flight_parameters['model']](filelist)

    def startLiveForecast(self, parameters, model_path=tempfile.gettempdir(), timestep=10):
        """
        Starts a live forecast.
        """
        self.flight_parameters = parameters
        self.model_path = model_path
        self.timestep = timestep
        self.segment_tracked = gpxpy.gpx.GPXTrackSegment()
        self.segment_tracked.points.append(gpxpy.gpx.GPXTrackPoint(
                parameters['launch_lat'],
                parameters['launch_lon'],
                elevation=parameters['launch_alt'],
                time=parameters['launch_datetime']))
        self.launch_point = gpxpy.gpx.GPXWaypoint(
                parameters['launch_lat'],
                parameters['launch_lon'],
                elevation=parameters['launch_alt'],
                time=parameters['launch_datetime'],
                name='Launch')
        self.top_point = None
        self.timeseries = {'DATETIME': [], 'PRESS': [], 'ALT': [], 'TEMP': [], 'BATTV': []}
        self.ui.label_ascent_status_value.setText('ascending')
        if self.comm_settings is None:
            self.onLoadConfig()
        try:
            self.message_handler.connect()
        except Exception as err:
            QMessageBox.critical(self, 'Connection error', f'Cannot connect to IMAP server: {err}')
            self.stopLiveForecast()
            return
        worker = Worker(self.downloadModelData, error_callback=self.showError)
        worker.signals.finished.connect(self.onWorkerFinished)
        worker.signals.finished.connect(self.timer.start)
        self.threadpool.start(worker)
        self.show()

    def stopLiveForecast(self):
        """
        Stops a live forecast.
        """
        self.timer.stop()
        if self.message_handler.isConnected():
            self.message_handler.disconnect()
        self.model_data = None
        self.stopLiveOperation.emit()

    def queryMessages(self):
        """
        Query new messages from server.
        """
        from_address = self.ui.combo_receive_imei.currentData() + '@rockblock.rock7.com'
        print("Querying messages from {} ...".format(from_address)) # DEBUG
        messages = self.message_handler.getDecodedMessages(from_address=from_address)
        if len(messages) > 0:
            logging.info('Received {} message(s).'.format(len(messages)))
            logging.info('Last: {}'.format(messages[-1]))
            is_invalid = np.zeros(len(messages), dtype=bool)
            for ind_msg in range(len(messages)):
                msg = messages[ind_msg]
                if 'LON' not in msg or 'LAT' not in msg or 'ALT' not in msg:
                    is_invalid[ind_msg] = True
                elif not trajectory_predictor.checkGeofence(
                        msg['LON'], msg['LAT'],
                        self.flight_parameters['launch_lon'],
                        self.flight_parameters['launch_lat'],
                        self.comm_settings['geofence']['radius']):
                    is_invalid[ind_msg] = True
                else:
                    self.segment_tracked.points.append(message.Message.message2trackpoint(msg))
                    self.appendTimeseries(msg)
            print('Valid messages: {}'.format(np.array(messages)[~is_invalid])) # DEBUG
            if not all(is_invalid):
                last_msg = np.array(messages)[~is_invalid][-1]
                self.setStandardData(last_msg)
                self.setAdvancedData(last_msg)
                self.plotStandardData()
                worker = Worker(self.doLiveForecast, last_msg, error_callback=self.showError)
                worker.signals.finished.connect(self.onWorkerFinished)
                self.threadpool.start(worker)

    def doLiveForecast(self, msg, progress_callback=None, error_callback=None):
        """
        Performs a live forecast.
        This function is usually started in a separate worker thread.
        """
        print('Starting forecast from message: {}'.format(msg)) # DEBUG
        self.ui.label_status.setText('Computing trajectory forecast.')
        if self.model_data is None:
            print('No model data present, downloading.') # DEBUG
            self.downloadModelData(error_callback=error_callback)
        if self.model_data is None:
            if callable(error_callback):
                error_callback('Cannot retrieve model data.')
            return
        if self.top_point is None:
            ind_top = trajectory_predictor.detectDescent(self.segment_tracked, self.flight_parameters['launch_alt'])
            print('ind_top', ind_top) # DEBUG
            if ind_top is not None: # descent detected
                top_track_point = self.segment_tracked.points[ind_top]
                self.top_point = gpxpy.gpx.GPXWaypoint(
                            top_track_point.latitude, top_track_point.longitude,
                            elevation=top_track_point.elevation,
                            time=top_track_point.time,
                            name='Ceiling')
                self.ui.label_ascent_status_value.setText('descending')
        if self.segment_tracked.points[-1].elevation > np.maximum(self.flight_parameters['top_altitude'], self.top_point.elevation if self.top_point is not None else 0.):
            logging.info('Balloon above top altitude. Assuming descent is imminent.')
            self.top_point = message.Message.message2waypoint(msg, name='Ceiling')
        track = gpxpy.gpx.GPXTrack()
        track.segments.append(self.segment_tracked)
        waypoints = [self.launch_point]
        if self.top_point is None:
            waypoints.append(message.Message.message2waypoint(msg, name='Current'))
            # Track if balloon is cut now.
            track_cut = deepcopy(track)
            segment_cut, lon_cut, lat_cut = trajectory_predictor.predictDescent(
                    self.segment_tracked.points[-1].time,
                    self.segment_tracked.points[-1].longitude,
                    self.segment_tracked.points[-1].latitude,
                    self.segment_tracked.points[-1].elevation,
                    self.flight_parameters['descent_velocity'],
                    self.flight_parameters['parachute_parameters'],
                    self.flight_parameters['payload_weight'],
                    self.flight_parameters['payload_area'],
                    self.model_data,
                    self.timestep)
            track_cut.segments.append(segment_cut)
            waypoints_cut = deepcopy(waypoints)
            waypoints_cut.append(gpxpy.gpx.GPXWaypoint(
                lat_cut, lon_cut,
                elevation=segment_cut.points[-1].elevation,
                time=segment_cut.points[-1].time, name='Landing (cut)'))
            # Track if flight continues as planned.
            segment_ascent, cur_lon, cur_lat, cur_datetime = trajectory_predictor.predictAscent(
                    self.segment_tracked.points[-1].time,
                    self.segment_tracked.points[-1].longitude,
                    self.segment_tracked.points[-1].latitude,
                    self.segment_tracked.points[-1].elevation,
                    self.flight_parameters['top_altitude'],
                    self.flight_parameters['ascent_velocity'],
                    self.model_data,
                    self.timestep)
            track.segments.append(segment_ascent)
            waypoints.append(gpxpy.gpx.GPXWaypoint(
                    cur_lat, cur_lon, elevation=self.flight_parameters['top_altitude'], time=cur_datetime, name='Ceiling'))
            initial_descent_velocity = 0.
        else:
            waypoints.append(self.top_point)
            waypoints.append(message.Message.message2waypoint(msg, name='Current'))
            cur_datetime = self.segment_tracked.points[-1].time
            cur_lon = self.segment_tracked.points[-1].longitude
            cur_lat = self.segment_tracked.points[-1].latitude
            cur_alt = self.segment_tracked.points[-1].elevation
            track_cut = None
            initial_descent_velocity = (self.segment_tracked.points[-1].elevation - self.segment_tracked.points[-2].elevation) / (self.segment_tracked.points[-1].time - self.segment_tracked.points[-2].time).total_seconds()
            print(initial_descent_velocity) # DEBUG
        segment_descent, landing_lon, landing_lat = trajectory_predictor.predictDescent(
                cur_datetime, cur_lon, cur_lat,
                self.flight_parameters['top_altitude'] if self.top_point is None else cur_alt,
                self.flight_parameters['descent_velocity'],
                self.flight_parameters['parachute_parameters'],
                self.flight_parameters['payload_weight'],
                self.flight_parameters['payload_area'],
                self.model_data,
                self.timestep,
                initial_velocity=initial_descent_velocity)
        flight_range = geog.distance(
                [self.flight_parameters['launch_lon'], self.flight_parameters['launch_lat']],
                [landing_lon, landing_lat]) / 1000.
        self.setLanding(segment_descent.points[-1].time, landing_lon, landing_lat, segment_descent.points[-1].elevation, flight_range)
        track.segments.append(segment_descent)
        waypoints.append(gpxpy.gpx.GPXWaypoint(
                landing_lat, landing_lon,
                elevation=segment_descent.points[-1].elevation,
                time=segment_descent.points[-1].time, name='Landing'))
        if self.comm_settings['output']['format'].lower() == 'kml':
            trajectory_predictor.writeKml(
                    track,
                    os.path.join(self.comm_settings['output']['directory'], self.comm_settings['output']['filename']),
                    waypoints=waypoints,
                    networklink=self.comm_settings['webserver']['networklink'],
                    refreshinterval=self.comm_settings['webserver']['refreshinterval'],
                    upload=self.comm_settings['webserver'])
            if track_cut:
                trajectory_predictor.writeKml(
                        track_cut,
                        os.path.join(self.comm_settings['output']['directory'], os.path.splitext(self.comm_settings['output']['filename'])[0]+'-cut.kml'),
                        waypoints=waypoints_cut,
                        upload=self.comm_settings['webserver'])
        else:
            trajectory_predictor.writeGpx(
                    track,
                    os.path.join(self.comm_settings['output']['directory'], self.comm_settings['output']['filename']),
                    waypoints=waypoints,
                    upload=self.comm_settings['webserver'])
            if track_cut:
                trajectory_predictor.writeGpx(
                        track_cut,
                        os.path.join(self.comm_settings['output']['directory'], os.path.splitext(self.comm_settings['output']['filename'])[0]+'-cut.gpx'),
                        waypoints=waypoints_cut,
                        upload=self.comm_settings['webserver'])
        if self.comm_settings['webserver']['webpage']:
            if track_cut:
                waypoints.append(waypoints_cut[-1]) # Add landing point if balloon is cut now.
            trajectory_predictor.createWebpage(track,
                          waypoints,
                          self.comm_settings['webserver']['webpage'],
                          upload=self.comm_settings['webserver'],
                          track_cut=track_cut)

    def sendIridiumMessage(self, imei, msg, username, password, progress_callback=None, error_callback=None):
        """
        Send an IRIDIUM message to a mobile device via RockBLOCK's web interface.
        This function can be executed in a separate worker thread.
        """
        success, message = self.message_handler.sendMessage(imei, msg, username, password)
        if success:
            self.ui.label_status.setText('Message sent.')
        else:
            self.ui.label_status.setText('Sending message failed.')
            if callable(error_callback):
                error_callback('Failed to send message: {}'.format(message))

    @Slot()
    def onLoadConfig(self):
        """
        Callback for load config button.
        """
        filename, filetype = QFileDialog.getOpenFileName(self, 'Open communication settings', None, 'Configuration files (*.ini);;All files (*)')
        if filename:
            self.loadConfig(filename)

    @Slot()
    def onChangeQueryTime(self, value):
        """
        Callback when query time is changed.
        """
        self.timer.setInterval(value * 60. * 1000.)

    @Slot()
    def onQueryNow(self):
        """
        Callback when query now button is clicked.
        """
        self.queryMessages()

    @Slot()
    def onSendIridium(self):
        """
        Callback for button to send IRIDIUM message.
        """
        data = {}
        if self.ui.check_cutter1.isChecked():
            data['USERFUNC1'] = 1
        if self.ui.check_cutter2.isChecked():
            data['USERFUNC2'] = 1
        msg = self.message_handler.encodeMessage(data)
        imei = self.ui.combo_iridium.currentData()
        logging.info('Sending message "{}" to IMEI {} ...'.format(message_sbd.MessageSbd.bin2asc(msg), imei))
        self.ui.label_status.setText('Sending message ...')
        worker = Worker(self.sendIridiumMessage, imei, msg, self.comm_settings['rockblock']['user'], self.comm_settings['rockblock']['password'], error_callback=self.showError)
        self.threadpool.start(worker)

    @Slot()
    def onComboPayloadChanged(self, value):
        print('onComboPayloadChanged', value) # DEBUG
        if self.ui.layout_advanced_payload_status.itemAt(1): print(self.ui.layout_advanced_payload_status.itemAt(1).widget()) # DEBUG
        if self.ui.layout_advanced_payload_status.count() > 1 and self.payloadwidget:
            self.ui.layout_advanced_payload_status.removeWidget(self.payloadwidget)
            self.payloadwidget.setParent(None)
            self.payloadwidget = None
        filename = self.ui.combo_payload_type.currentData()
        if filename is not None:
            ui_file = QFile(filename)
            if not ui_file.open(QFile.ReadOnly):
                QMessageBox.critical(self, 'Internal error', f'Cannot open {filename}: {ui_file.errorString()}')
                return
            loader = QUiLoader()
            self.payloadwidget = loader.load(ui_file)
            ui_file.close()
            self.payloadwidget.show()
            self.ui.layout_advanced_payload_status.addWidget(self.payloadwidget)

    @Slot()
    def onWorkerFinished(self):
        """
        Callback to be executed when a thread finishes.
        """
        self.ui.label_status.setText('Idle.')

    @Slot()
    def showError(self, message):
        """
        Callback to be executed when a thread produces an error.
        """
        QMessageBox.critical(self, 'Balloon operator', message)


""" Script main ===============================================================
"""
if __name__ == "__main__":
    parser = argparse.ArgumentParser('Balloon ooperator GUI')
    parser.add_argument('-p', '--payload', required=False, default=None, help='Load payload configuration from ini file')
    parser.add_argument('-c', '--config', required=False, default=None, help='Load configuration for operator from ini file')
    parser.add_argument('-b', '--balloon-param', required=False, default='totex_balloon_parameters.tsv', help='Balloon parameter file')
    parser.add_argument('--parachute-param', required=False, default='parachute_parameters.tsv', help='Parachute parameter file')
    args = parser.parse_args()

    app = QApplication(sys.argv)

    main_widget = MainWidget()
    if args.payload:
        main_widget.loadPayloadIni(args.payload)
    else:
        main_widget.loadBalloonParameters(args.balloon_param)
        main_widget.loadParachuteParameters(args.parachute_param)
    if args.config:
        main_widget.operator_widget.loadConfig(args.config)
    main_widget.show()

    sys.exit(app.exec())
