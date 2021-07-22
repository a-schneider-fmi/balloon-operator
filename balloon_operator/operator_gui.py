#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graphical user interface for the balloon operator.

Created on Wed Jul 21 18:34:53 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox
from PySide6.QtCore import Slot, Signal, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QIcon, QPixmap
from gui_mainwidget import Ui_MainWidget
import gui_icons
from balloon_operator import filling, parachute, trajectory_predictor, download_model_data
import configparser
import datetime
import argparse
import tempfile
import numpy as np
import os.path
import traceback
import logging


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

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

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

        self.ui.dt_launch_datetime.setDateTime(datetime.datetime.utcnow())
        for fill_gas in filling.FillGas:
            self.ui.combo_fill_gas.addItem(filling.fill_gas_names[fill_gas], fill_gas)
        self.ui.edit_output_file.setText(os.path.join(tempfile.gettempdir(), 'trajectory.gpx'))
        self.balloon_parameter_list = np.zeros((3,0), dtype=[('weight', 'f8'), ('burst_diameter', 'f8'), ('drag_coefficient', 'f8')])
        self.balloon_parameter_file = None
        self.parachute_parameter_list = np.zeros((3,0), dtype=[('name', 'U25'), ('diameter', 'f8'), ('drag_coefficient', 'f8')])
        self.parachute_parameter_file = None
        self.balloon_performance = {}
        self.timestep = 10
        self.model_path = tempfile.gettempdir()

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
        self.ui.button_output_file_dialog.clicked.connect(self.onOutputFileSelector)
        self.ui.button_forecast.clicked.connect(self.onForecast)

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
            self.ui.spin_cut_altitude.setValue(config['payload'].getfloat('cut_altitude', fallback=0.))
            if 'cut_altitude' in config['payload']:
                self.ui.check_cut.setChecked(True)
                self.ui.spin_cut_altitude.setEnabled(True)
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

    def computeBalloonPerformance(self):
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

    def setResult(self, longitude, latitude, altitude, flight_range):
        self.ui.label_landing_longitude_value.setText('{:.5f}°'.format(longitude))
        self.ui.label_landing_latitude_value.setText('{:.5f}°'.format(latitude))
        self.ui.label_landing_altitude_value.setText('{:.0f} m'.format(altitude))
        self.ui.label_range_value.setText('{:.0f} km'.format(flight_range))

    def doForecast(self, parameters, progress_callback=None):
        # Download and read in model data.
        model_filenames = download_model_data.getGfsData(
                parameters['launch_lon'], parameters['launch_lat'],
                parameters['launch_datetime'], self.model_path)
        if model_filenames is None:
            QMessageBox.critical(self, 'Data retrieval error', 'Error retrieving model data.')
            return None
        model_data = trajectory_predictor.readGfsDataFiles(model_filenames)
    
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
        self.setResult(track.segments[-1].points[-1].longitude, track.segments[-1].points[-1].latitude, track.segments[-1].points[-1].elevation, flight_range)

        # Save resulting trajectory.
        output_file = parameters['output_file']
        output_ext = os.path.splitext(output_file)[1]
        if output_ext.lower() == '.kml':
            trajectory_predictor.writeKml(track, output_file, waypoints=waypoints)
        else:
            trajectory_predictor.writeGpx(track, output_file, waypoints=waypoints, description=track.description)
        return {'lon': track.segments[-1].points[-1].longitude,
                'lat': track.segments[-1].points[-1].latitude,
                'alt': track.segments[-1].points[-1].elevation,
                'range': flight_range,
                'top_alt': parameters['top_altitude']}

    @Slot()
    def onLoadPayload(self):
        filename = QFileDialog.getOpenFileName(self, 'Open payload information', None, 'Configuration files (*.ini);;All files (*)')
        self.loadPayloadIni(filename)

    @Slot()
    def onSavePayload(self):
        filename, filetype = QFileDialog.getSaveFileName(self, 'Save payload information', None, 'Configuration files (*.ini);;All files (*)')
        if filename:
            if os.path.splitext(filename)[1].lower() != '.ini':
                filename += '.ini'
            self.savePayloadIni(filename)

    @Slot()
    def onChangeCheckDescentBalloon(self, new_state):
        self.ui.combo_desc_balloon.setEnabled(new_state)
        self.ui.spin_desc_velocity.setEnabled(new_state)
        self.computeBalloonPerformance()

    @Slot()
    def onChangeCheckCut(self, new_state):
        self.ui.spin_cut_altitude.setEnabled(new_state)

    @Slot()
    def onChangeBalloonParameter(self, value):
        self.computeBalloonPerformance()

    @Slot()
    def onOutputFileSelector(self):
        output_file, filetype = QFileDialog.getSaveFileName(self, 'Save trajectory', os.path.dirname(self.ui.edit_output_file.text()), 'GPX tracks (*.gpx);;KML tracks (*.kml)')
        if output_file:
            if filetype == 'GPX tracks (*.gpx)' and os.path.splitext(output_file)[1].lower() != '.gpx':
                output_file += '.gpx'
            if filetype == 'KML tracks (*.kml)' and os.path.splitext(output_file)[1].lower() != '.kml':
                output_file += '.kml'
            self.ui.edit_output_file.setText(output_file)

    @Slot()
    def forecastComplete(self):
        self.ui.button_forecast.setEnabled(True)

    @Slot()
    def forecastResult(self, result):
        print(result)

    @Slot()
    def onForecast(self):
        self.ui.button_forecast.setEnabled(False)
        parameters = {
                'parachute_parameters': parachute.lookupParachuteParameters(self.parachute_parameter_list, self.ui.combo_parachute.currentText()),
                'payload_area': self.ui.spin_payload_area.value(),
                'launch_lon': self.ui.spin_launch_longitude.value(),
                'launch_lat': self.ui.spin_launch_latitude.value(),
                'launch_alt': self.ui.spin_launch_altitude.value(),
                'launch_datetime': self.ui.dt_launch_datetime.dateTime().toPython(),
                'output_file': self.ui.edit_output_file.text()
                }
        if self.ui.check_cut.isChecked():
            parameters['top_altitude'] = np.minimum(self.ui.spin_cut_altitude.value(), self.balloon_performance['ascent_burst_height'])
        else:
            parameters['top_altitude'] = self.balloon_performance['ascent_burst_height']
        parameters.update(self.balloon_performance)

        # Execute calculation in a separate thread in order not to make the GUI unresponsive.
        worker = Worker(self.doForecast, parameters) # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.forecastResult)
        worker.signals.finished.connect(self.forecastComplete)
        self.threadpool.start(worker)


""" Script main ===============================================================
"""
if __name__ == "__main__":
    parser = argparse.ArgumentParser('Balloon ooperator GUI')
    parser.add_argument('-p', '--payload', required=False, default=None, help='Load payload configuration from ini file')
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
    main_widget.show()

    sys.exit(app.exec())
