from PyQt5 import QtWidgets, uic
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
import sys  # We need sys so that we can pass argv to QApplication
import os

DEFAULT_TARGET_VOLT = 330

target_v = DEFAULT_TARGET_VOLT
actual_v = 0.0
actual_a = 0.0
actual_t = 0.0

fan_mode = 0

# I tought that to update the status periodically i could use a timer, every second for example,
# and when the timer expires an event is raised, listening to that event, i could update every value,
# or change the status ecc..

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        #Load the UI Page
        uic.loadUi('main.ui', self)

        self.plot([1,2,3,4,5,6,7,8,9,10], [30,32,34,32,33,31,29,32,35,45])
        #self.init()
        self.b_next.clicked.connect(self.check)

    def init(self):
        self.l_status.setText("init")
        self.l_pork_connected.setText("not connected")
        self.l_brusa_connected.setText("not connected")
        self.l_volts.setText("0")
        self.l_amperes.setText("0")
        self.l_temp.setText("0")
        self.button_charge.setEnabled(False)

    def check(self):
        self.l_status.setText("check")

    def plot(self, hour, temperature):
        self.A_graph.plot(hour, temperature)


app = QtWidgets.QApplication(sys.argv)
main = MainWindow()
main.show()

app.exec_()



