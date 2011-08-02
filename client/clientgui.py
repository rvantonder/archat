#!/usr/bin/env python

import sip
sip.setapi('QVariant', 2)
import sys
from subprocess import Popen
import subprocess
from client import Client  #import the client
import select
import threading
from logger import Logger
import socket
import pickle
import os

from PyQt4 import QtCore, QtGui
from clientwindow import Ui_Form

class ClientForm(QtGui.QWidget, QtCore.QThread):
  def __init__(self, host, port):
    super(ClientForm, self).__init__()
    self.client = Client(host,port)
    self.ui = Ui_Form()
    self.ui.setupUi(self)
    self.ui.lineEdit.setFocus()
    self.icon = QtGui.QIcon('creeper.tif')
    self.auth = False
    self.colour_list = (QtCore.Qt.red, QtCore.Qt.darkRed, QtCore.Qt.blue, QtCore.Qt.darkGreen, QtCore.Qt.magenta, QtCore.Qt.darkBlue, QtCore.Qt.darkCyan,QtCore.Qt.darkMagenta, QtCore.Qt.darkYellow, QtCore.Qt.darkGray, QtGui.QColor('#00CC99'), QtGui.QColor('#0099FF'), QtGui.QColor('#005555'), QtGui.QColor('#FF6600'), QtGui.QColor('#660033'), QtGui.QColor('#9900FF'))
    self.user_colour_list = {}
    self.running = 1
    if os.path.isfile('client.log'):
      os.remove('client.log')
    self.clientLogger = Logger('client.log')

    self.createActions()
    self.createTrayIcon()
    self.trayIcon.activated.connect(self.iconActivated)
    self.trayIcon.show()
    
  def iconActivated(self, event):
      if event in (QtGui.QSystemTrayIcon.Trigger, QtGui.QSystemTrayIcon.DoubleClick):
          self.showNormal()
          #self.previewWindow.show() #normal, if wanted
    
  def createTrayIcon(self):
      self.trayIconMenu = QtGui.QMenu(self)
      self.trayIconMenu.addAction(self.minimizeAction)
      self.trayIconMenu.addAction(self.maximizeAction)
      self.trayIconMenu.addAction(self.restoreAction)
      self.trayIconMenu.addSeparator()
      self.trayIconMenu.addAction(self.quitAction)
        

      self.trayIcon = QtGui.QSystemTrayIcon(self)
      self.trayIcon.setIcon(QtGui.QIcon('tray.png'))
      self.trayIcon.setContextMenu(self.trayIconMenu)
         
         
  def createActions(self):
    self.minimizeAction = QtGui.QAction("Mi&nimize", self,
            triggered=self.hide)

    self.maximizeAction = QtGui.QAction("Ma&ximize", self,
            triggered=self.showMaximized)

    self.restoreAction = QtGui.QAction("&Restore", self,
            triggered=self.showNormal)

    self.quitAction = QtGui.QAction("&Quit", self,
            triggered=QtGui.qApp.quit)
         
  def closeEvent(self, event):
      if self.trayIcon.isVisible():
          #QtGui.QMessageBox.information(self, "Systray",
              #"Program continues running in tray")
          self.hide()
          event.ignore()


  def parse_msg(self, msg): 
  
    try:
      user,msg = msg.split(': ',1) 
      try:
        if msg.startswith('(l'): #then it is a pickle, if not just display message TODO
          userlist = pickle.loads(msg)

          userlist.sort()

          for i in userlist:
            if not (str(i) in self.user_colour_list):
              self.user_colour_list[str(i)] = self.colour_list[len(self.user_colour_list)%len(self.colour_list)]
          
          self.ui.listWidget.clear() #delete the whole thing

          for user in userlist: 
            n = QtGui.QListWidgetItem(self.icon, str(user))
            n.setTextColor(self.user_colour_list[str(user)])
            self.ui.listWidget.addItem(n)
        elif msg == 'TERMINATE':
          self.running = 0
          self.clientLogger.logger.info("Server Termination")
          return
        else: 
          self.ui.textEdit.setTextColor(self.user_colour_list.get(str(user), QtCore.Qt.black))
          self.ui.textEdit.append(user+': '+msg)
          self.ui.textEdit.ensureCursorVisible() #this will scroll it down

      except EOFError: #if the user sends data that seems like a pickle
        self.ui.textEdit.append(user+': '+msg) #just do this
    except ValueError:
      self.ui.textEdit.setTextColor(QtCore.Qt.black)
      self.ui.textEdit.append(msg)
      self.ui.textEdit.ensureCursorVisible() #whisper

  def request_username(self):
    try:
      self.client.open_socket()
    except socket.error:
      self.ui.textEdit.append("[ERROR] Server is not accepting connections") 
      self.clientLogger.logger.warn("Server is not accepting connections")
      return

    while 1: #loop until accepted
        response = self.client.socket.recv(self.client.size)
        if response == 'REJECT':
          self.ui.textEdit.setTextColor(QtCore.Qt.black)
          self.ui.textEdit.append('Username rejected -- already in use') #TODO server should say this nicely
          self.ui.lineEdit.setText('Enter username') #sometimes it 'skips' over this. no idea why; try not having focus here when settin
          self.client.close_socket()
          self.client.open_socket()
        elif response == 'ACCEPT':
          self.clientLogger.logger.info('Username accepted')
          break #get out
          
    self.auth = True #if accepted
    self.clientLogger.logger.info('Authorized')

  def run(self):       
    self.clientLogger.logger.info('Running')

    self.request_username() #a loop until an acceptable username is given

    while self.running:
      try:
        response = self.client.socket.recv(self.client.size)
      except socket.error:
        self.clientLogger.logger.warn('Response error from server')
        self.client.close_socket()
        self.clientLogger.logger.info("Socket closed")
        return
      try:
        self.parse_msg(response)
      except UnboundLocalError:
        pass  
          
    self.client.close_socket()
    self.clientLogger.logger.info("Socket closed")

  def on_lineEdit_returnPressed(self):
    if self.ui.lineEdit.displayText() != '':
      stringToSend = self.ui.lineEdit.displayText()

      self.clientLogger.logger.info('Would like to send '+stringToSend)
      if not self.auth:
        try:
          self.client.socket.send('request:'+str(stringToSend)) #its a username request
        except socket.error:
          self.ui.textEdit.setText('[ERROR] Server is not accepting connections')
          self.clientLogger.logger.info('Sending request for username '+stringToSend)
      else:
        try:
          self.client.socket.send(str(stringToSend)) #cast qt string
        except socket.error:
          self.ui.textEdit.setTextColor(QtCore.Qt.black)
          self.ui.textEdit.setText('The connection with the server has been lost, please restart the client.')
          self.clientLogger.logger.info('Connection with the server has been lost.')
          self.ui.listWidget.clear() #delete the whole thing
              
    self.ui.lineEdit.setText('')

if __name__ == '__main__':
  gui = ClientForm('localhost',3001)
  clientLogger.logger.info('sockets set up, starting thread')

  t = threading.Thread(target=gui.run)
  t.setDaemon(True) #Sometimes programs spawn a thread as a daemon that runs without blocking the main program from exiting. Using daemon threads is useful for services where there may not be an easy way to interrupt the thread or where letting the thread die in the middle of its work does not lose or corrupt data
  t.start()
  clientLogger.logger.info('showing gui')
  gui.show()
  sys.exit(app.exec_())
