# This Python file uses the following encoding: utf-8
import os
from pathlib import Path
import sys

import requests
import asyncio
import pproxy

import nest_asyncio
nest_asyncio.apply()


from PySide6.QtWidgets import QApplication, QWidget, QListWidgetItem, QSystemTrayIcon
from PySide6.QtCore import QFile, QThread, Qt, QEvent, Slot
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QIcon

nodes = {}


class ProxyThread(QThread):
    def __init__(self, parent = None):
        QThread.__init__(self, parent)
        self.command = ""

    def set_connection(self, command):
        self.command = command

    def run(self):
        server = pproxy.Server('tunnel://127.0.0.1:1234')
        remote = pproxy.Connection(self.command)
        args = dict( rserver = [remote],
                     verbose = print )

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.handler = self.loop.run_until_complete(server.start_server(args))
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.handler.close)
        self.loop.call_soon_threadsafe(self.handler.wait_closed)
        self.loop.call_soon_threadsafe(self.loop.shutdown_asyncgens)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop.close()
        


class MainWindow(QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.systemTrayIcon = QSystemTrayIcon(self)
        self.systemTrayIcon.setIcon(QIcon("icon.ico"))
        self.systemTrayIcon.setVisible(True)
        self.systemTrayIcon.activated.connect(self.on_systemTrayIcon_activated)
        self.load_ui_addnode()
        self.load_ui()

    @Slot(QSystemTrayIcon.ActivationReason)
    def on_systemTrayIcon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            print(self.isHidden())
            if self.isHidden():
                self.show()
            else:
                self.hide()

    # def changeEvent(self, event):
    #     if event.type() == QEvent.WindowStateChange:
    #         if self.windowState() & Qt.WindowMinimized:
    #             self.hide()
    #             event.ignore()
                

    #     super(MainWindow, self).changeEvent(event)

    def load_ui(self):
        loader = QUiLoader()
        path = os.fspath("mainwindow.ui")
        ui_file = QFile(path)
        ui_file.open(QFile.ReadOnly)
        self.windo_mainwindow = loader.load(ui_file, self)
        self.load_nodes()
        self.windo_mainwindow.pushButton_addnode.clicked.connect(self.show_window_addnode)
        self.windo_mainwindow.pushButton_removenode.clicked.connect(self.remove_node)

        self.proxythread = ProxyThread()

        self.windo_mainwindow.pushButton_connect.clicked.connect(self.start_proxy)
        self.windo_mainwindow.pushButton_disconnect.clicked.connect(self.stop_proxy)

        self.windo_mainwindow.actionConnectivity_check.triggered.connect(self.connectivity_check)

        ui_file.close()

    def start_proxy(self):
        connection_name = self.windo_mainwindow.listWidget_nodes.currentItem().text()
        self.proxythread.set_connection(nodes[connection_name])
        self.proxythread.start()
        self.windo_mainwindow.textEdit_log.append("[+] Proxy started")


    def stop_proxy(self):
        self.windo_mainwindow.textEdit_log.append("[+] Proxy Stopped")
        self.proxythread.stop()

    def load_ui_addnode(self):
        loader = QUiLoader()
        path = os.fspath("addnode.ui")
        ui_file = QFile(path)
        ui_file.open(QFile.ReadOnly)
        self.window_addnode = loader.load(ui_file, self)
        self.window_addnode.pushButton_save.clicked.connect(self.add_node)
        ui_file.close()

    def show_window_addnode(self):
        self.window_addnode.show()


    def add_node(self):

        name = self.window_addnode.lineEdit_name.text()
        command = ""

        if self.window_addnode.radioButton_addcommand.isChecked():
            command = self.window_addnode.lineEdit_command.text()
        else:
            command = command + self.window_addnode.comboBox_protocol.currentText()
            command = command + "://" + self.window_addnode.lineEdit_host.text()
            command = command + ":" + self.window_addnode.lineEdit_port.text()
            if self.window_addnode.checkBox_auth.isChecked():
                command = command + "#" + self.window_addnode.lineEdit_username.text()
                command = command + ":" + self.window_addnode.lineEdit_password.text()
            pass

        self.write_to_db(name, command)
        self.windo_mainwindow.textEdit_log.append("[+] Added new node")
        self.windo_mainwindow.textEdit_log.append(f"[*] {name} -> {command}")
        self.load_nodes()

    def remove_node(self):
        # get current row and delete it
        selected_node = self.windo_mainwindow.listWidget_nodes.currentRow()

        connection_name = self.windo_mainwindow.listWidget_nodes.currentItem().text()

        self.windo_mainwindow.listWidget_nodes.takeItem(selected_node)


        with open("nodes.dat", "r") as f:
            lines = f.readlines()

        with open("nodes.dat", "w") as f:
            for line in lines:
                name, _ = line.strip().split("||")
                if not name == connection_name:                  
                    f.write(line)


    def write_to_db(self, name, command):
        with open("nodes.dat", "a") as f:
            f.write(f"{name}||{command}\n")

    def load_nodes(self):
        self.windo_mainwindow.listWidget_nodes.clear()
        with open("nodes.dat", "r") as f:
            for line in f:
                name, command = line.strip().split("||")
                nodes[name] = command
                item = QListWidgetItem(name)
                self.windo_mainwindow.listWidget_nodes.addItem(item)

        self.windo_mainwindow.textEdit_log.append("[+] Loaded nodes")


    def connectivity_check(self):
        http_proxy  = "socks5://127.0.0.1:1234"
        https_proxy = "socks5://127.0.0.1:1234"

        proxyDict = {
                      "http"  : http_proxy,
                      "https"   : https_proxy
                    }

        self.windo_mainwindow.textEdit_log.append("[+] Started connectivity check")
        try:
            result = requests.get("http://ident.me", timeout=3, proxies=proxyDict)
            self.windo_mainwindow.textEdit_log.append(f"[*] Connectivity check status: {result.status_code}")
        except:
            self.windo_mainwindow.textEdit_log.append(f"[*] Connectivity check status: not connected")








if __name__ == "__main__":
    #
    app = QApplication([])
    window = MainWindow()
    window.setFixedSize(300, 500)
    window.setWindowTitle("TProxy")
    window.show()
    sys.exit(app.exec())
