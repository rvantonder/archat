import threading
from clientgui import ClientForm
from PyQt4 import QtCore, QtGui
import sys

if __name__ == '__main__':
    try:
      app = QtGui.QApplication(sys.argv)
      gui = ClientForm(sys.argv[1], int(sys.argv[2]))
      t = threading.Thread(target=gui.run)
      t.setDaemon(True)
      t.start()
      gui.show()
      sys.exit(app.exec_())
    except IndexError:
      print 'Usage: python main.py <server> <port>'


