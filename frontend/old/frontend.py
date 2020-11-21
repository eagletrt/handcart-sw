from PyQt5 import QtWidgets, uic
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
import sys  # We need sys so that we can pass argv to QApplication
import os

#tickle  qml da guardare per implementare gui

DEFAULT_TARGET_VOLT = 330

target_v = DEFAULT_TARGET_VOLT
actual_v = 0.0
actual_a = 0.0
actual_t = 0.0

fan_mode = -1 #-1 is auto


# I tought that to update the status periodically i could use a timer, every second for example,
# and when the timer expires an event is raised, listening to that event, i could update every value,
# or change the status ecc..

class targetVWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(targetVWindow, self).__init__(parent)
        uic.loadUi('targetVWindow.ui', self)

        self.b_save.clicked.connect(self.on_pushButton_b_save)

        self.tVolt.setMaximum(400)
        self.tVolt.setValue(target_v)
        if (target_v == DEFAULT_TARGET_VOLT):
            self.cb_default.setChecked(True)
            self.tVolt.setEnabled(False)

        self.cb_default.stateChanged.connect(self.on_checkboxChanged_cb_default)

    def on_checkboxChanged_cb_default(self):
        if (not self.cb_default.isChecked()):
            self.tVolt.setValue(DEFAULT_TARGET_VOLT)
            self.tVolt.setEnabled(True)
        else:
            self.tVolt.setEnabled(False)

    def on_pushButton_b_save(self):
        # implementare invio messaggio
        pass

class fanCtlWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(fanCtlWindow, self).__init__(parent)
        uic.loadUi('fanCtlWindow.ui', self)

        self.slider_fanspeed.setMinimum(0)
        self.slider_fanspeed.setMaximum(100)

        if (fan_mode == -1):
            self.cb_auto.setChecked(True)
            self.slider_fanspeed.setEnabled(False)

        self.cb_auto.stateChanged.connect(self.on_checkboxChanged_cb_auto)

    def on_checkboxChanged_cb_auto(self):
        if self.cb_auto.isChecked():
            self.slider_fanspeed.setEnabled(False)
        else:
            self.slider_fanspeed.setEnabled(True)

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        # Load the UI Page
        uic.loadUi('main.ui', self)

        self.plot([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [30, 32, 34, 32, 33, 31, 29, 32, 35, 45])

        self.b_next.clicked.connect(self.s_ready)
        self.b_targetV.clicked.connect(self.on_pushButton_b_targetV)
        self.b_fanctl.clicked.connect(self.on_pushButton_b_fanctl)

    def s_init(self):
        self.l_status.setText("init")
        self.l_pork_connected.setText("not connected")
        self.l_brusa_connected.setText("not connected")
        self.l_volts.setText("0")
        self.l_amperes.setText("0")
        self.l_temp.setText("0")
        self.button_charge.setEnabled(False)

    def s_check(self):
        self.l_status.setText("check")

    def s_precharge(self):
        self.l_status.setText("precharge")

    def s_ready(self):
        self.l_status.setText("ready")
        self.b_charge.setText("CHARGE")

    def s_charge(self):
        self.l_status.setText("check")

    def s_c_done(self):
        self.l_status.setText("c_done")

    def s_error(self):
        self.l_status.setText("error")
        self.l_status.setStyleSheet('color:red')
        self.b_charge.setText("RESET")

    def plot(self, hour, temperature):
        self.A_graph.plot(hour, temperature)

    def clock(self):
        pass
        # update all values and check for errors?

    def on_pushButton_b_targetV(self):
        dialog = targetVWindow(self)
        dialog.show()

    def on_pushButton_b_fanctl(self):
        dialog = fanCtlWindow(self)
        dialog.show()


app = QtWidgets.QApplication(sys.argv)
main = MainWindow()
main.show()

app.exec_()
