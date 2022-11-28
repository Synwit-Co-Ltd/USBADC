#! python3
import os
import sys
import collections
import configparser

from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtChart import QChart, QChartView, QLineSeries

os.environ['PATH'] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + os.environ['PATH']
from interface import USB_BACKEND, HID_BACKEND


N_CHNL = 8  # ADC Channel Count


'''
from USBHID_UI import Ui_USBHID
class USBHID(QWidget, Ui_USBHID):
    def __init__(self, parent=None):
        super(USBHID, self).__init__(parent)
        
        self.setupUi(self)
'''
class USBHID(QWidget):
    def __init__(self, parent=None):
        super(USBHID, self).__init__(parent)
        
        uic.loadUi('USBADC.ui', self)

        self.devices = self.get_devices()
        self.cmbPort.addItems(self.devices.keys())

        self.initSetting()

        self.initQwtPlot()

        self.tmrRcv = QtCore.QTimer()
        self.tmrRcv.setInterval(10)
        self.tmrRcv.timeout.connect(self.on_tmrRcv_timeout)
        self.tmrRcv.start()

        self.tmrRcv_Cnt = 0
    
    def get_devices(self):
        hids = HID_BACKEND.get_all_connected_interfaces()
        hids = [(f'HID: {dev.info()}', dev) for dev in hids]
        #usbs = USB_BACKEND.get_all_connected_interfaces()
        #usbs = [(f'USB: {dev.info()}', dev) for dev in usbs]

        return collections.OrderedDict(hids) # + usbs)

    def initSetting(self):
        if not os.path.exists('setting.ini'):
            open('setting.ini', 'w', encoding='utf-8')
        
        self.conf = configparser.ConfigParser()
        self.conf.read('setting.ini', encoding='utf-8')
        
        if not self.conf.has_section('HID'):
            self.conf.add_section('HID')
            self.conf.set('HID', 'port', '')

        if not self.conf.has_section('ADC'):
            self.conf.add_section('ADC')
            self.conf.set('ADC', 'chnl', '0x01')

        index = self.cmbPort.findText(self.conf.get('HID', 'port'))
        self.cmbPort.setCurrentIndex(index if index != -1 else 0)

        try:
            self.adcChnl = int(self.conf.get('ADC', 'chnl'), 16)
        except:
            self.adcChnl = 0x01

        for i in range(N_CHNL):
            if self.adcChnl & (1 << i):
                eval(f'self.chkCH{i+1}').setCheckState(Qt.Checked)

        for i in range(N_CHNL):
            eval(f'self.chkCH{i+1}').stateChanged.connect(lambda state, chnl=i: self.on_chkCHx_stateChanged(state, chnl))

    def initQwtPlot(self):
        self.PlotData  = [[0                    for j in range(1000)] for i in range(N_CHNL)]
        self.PlotPoint = [[QtCore.QPointF(j, 0) for j in range(1000)] for i in range(N_CHNL)]

        self.PlotChart = QChart()

        self.ChartView = QChartView(self.PlotChart)
        self.ChartView.setVisible(False)
        self.vLayout.insertWidget(1, self.ChartView)
        
        self.PlotCurve = []
        for i in range(N_CHNL):
            self.PlotCurve.append(QLineSeries())
            self.PlotCurve[i].setName(f'CH{i+1}')

        for i in range(N_CHNL):
            if self.adcChnl & (1 << i):
                self.PlotChart.addSeries(self.PlotCurve[i])
        self.PlotChart.createDefaultAxes()

    def on_chkCHx_stateChanged(self, state, chnl):
        if state == Qt.Checked:
            self.adcChnl |=  (1 << chnl)

            self.PlotChart.addSeries(self.PlotCurve[chnl])

        else:
            self.adcChnl &= ~(1 << chnl)

            self.PlotChart.removeSeries(self.PlotCurve[chnl])

        self.PlotChart.createDefaultAxes()

    @pyqtSlot(int)
    def on_chkWave_stateChanged(self, state):
        self.ChartView.setVisible(state == Qt.Checked)
        self.txtMain.setVisible(state == Qt.Unchecked)

    @pyqtSlot()
    def on_btnOpen_clicked(self):
        if self.btnOpen.text() == '打开连接':
            try:
                self.dev = self.devices[self.cmbPort.currentText()]
                self.dev.open()
            except Exception as e:
                print(e)
            else:
                self.cmbPort.setEnabled(False)
                self.btnOpen.setText('断开连接')
        else:
            self.dev.close()

            self.cmbPort.setEnabled(True)
            self.btnOpen.setText('打开连接')

    def on_tmrRcv_timeout(self):
        self.tmrRcv_Cnt += 1

        if self.btnOpen.text() == '断开连接':
            data = self.dev.read()
            if len(data) != N_CHNL*2:  # 2-byte per channel
                return

            data = [dl | (dh << 8) for (dl, dh) in zip(data[0::2], data[1::2])]

            if self.chkWave.isChecked():
                for i, y in enumerate(data):
                    self.PlotData[i].pop(0)
                    self.PlotData[i].append(y)
                    self.PlotPoint[i].pop(0)
                    self.PlotPoint[i].append(QtCore.QPointF(0, y))

                if self.tmrRcv_Cnt % 4 == 0:
                    for i in range(N_CHNL):
                        for j, point in enumerate(self.PlotPoint[i]):
                            point.setX(j)
                    
                        self.PlotCurve[i].replace(self.PlotPoint[i])
                    
                    miny, maxy = [], []
                    for i in range(N_CHNL):
                        if self.adcChnl & (1 << i):
                            miny.append(min(self.PlotData[i]))
                            maxy.append(max(self.PlotData[i]))

                    if miny and maxy:
                        miny, maxy = min(miny), max(maxy)
                    
                        self.PlotChart.axisY().setRange(miny, maxy)
                        self.PlotChart.axisX().setRange(0000, 1000)

            else:
                text = '   '.join([f'{data[i]:03X}' for i in range(N_CHNL) if self.adcChnl & (1 << i)])

                if len(self.txtMain.toPlainText()) > 25000: self.txtMain.clear()
                self.txtMain.append(text)
        
        else:
            if self.tmrRcv_Cnt % 100 == 0:
                devices = self.get_devices()
                if len(devices) != self.cmbPort.count():
                    self.devices = devices
                    self.cmbPort.clear()
                    self.cmbPort.addItems(devices.keys())
    
    def closeEvent(self, evt):
        self.conf.set('HID', 'port', self.cmbPort.currentText())
        self.conf.set('ADC', 'chnl', f'0x{self.adcChnl:02X}')
        self.conf.write(open('setting.ini', 'w', encoding='utf-8'))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    usb = USBHID()
    usb.show()
    app.exec()
