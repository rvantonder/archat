#!/usr/bin/env python

"""
An echo server that uses threads to handle multiple clients at a time.
Entering any line of input at the terminal will exit the server.
"""

import select
import socket
import sys
import threading
import logging
import os
import pickle
import time

global connections

class ServerLogger:
  def __init__(self, logfilename):
    if os.path.isfile(logfilename):
      os.remove(logfilename)

    self.logger = logging.getLogger("serverlogger")
    self.hdlr = logging.FileHandler(logfilename)
    self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(threadName)s %(message)s')
    self.hdlr.setFormatter(self.formatter)
    self.logger.addHandler(self.hdlr)
    self.logger.setLevel(logging.INFO)

def isOpen(ip,port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      s.connect((ip, port))
      s.shutdown(2)
      serverLogger.logger.info('port '+str(port)+' open')
    except:
      serverLogger.logger.warn('port '+str(port)+' blocked')

class Server:
  def __init__(self, port):
    self.host = ''
    self.port = port 
    self.backlog = 5
    self.size = 1024
    self.socket = None
    self.threads = []

  def open_socket(self):
    serverLogger.logger.info("Attempting to open socket")
    try:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        a = self.socket.bind((self.host,self.port))
        b =self.socket.listen(self.backlog)
    except socket.error, (value,message):
        if self.socket:
            self.socket.close()
        serverLogger.logger.warn("Could not open socket")
        print "Could not open socket: " + message
        sys.exit(1)
    serverLogger.logger.info("Socket open")

  def run(self):
    self.open_socket()
    input = [self.socket,sys.stdin]
    running = 1

    serverLogger.logger.info("Running")
    while running:
        inputready,outputready,exceptready = select.select(input,[],[])

        for s in inputready:

            if s == self.socket:
                serverLogger.logger.info("New connection incoming")  
                c = Client(self.socket.accept())
                c.setDaemon(True)
                c.start()
                self.threads.append(c)

            elif s == sys.stdin:
                # handle standard input
                junk = sys.stdin.readline()
                running = 0

    serverLogger.logger.info('Server shutdown requested.')
    serverLogger.logger.info('Close client sockets.')
    self.close_clients() #tell clients to close open connections
  
    serverLogger.logger.info('Closing server socket')
    self.socket.close()

    serverLogger.logger.info('Terminating client threads')
    for c in self.threads:
        c.join()

    serverLogger.logger.info('Client threads terminated')

  def close_clients(self):
    for socket in connections.values():
      socket.send('[SERVER]: TERMINATE') 

class Client(threading.Thread): #client thread
  def __init__(self,(client,address)):
    threading.Thread.__init__(self) 
    self.client = client #the socket
    self.address = address #the address
    self.size = 1024 #the message size
    self.username = None
    self.running = 1 #running state variable

  def parse_message(self, data):
    temp = data.split(':',1) #will ensure that there are at most two values, otherwise fuckup if more than one colon
    if len(temp) == 2:
        user = temp[0]
        msg = temp[1]
    else: 
        user = 'all'
        msg = temp[0]
    return (user, msg)

  def whisper(self, user, msg):
     if connections.has_key(user):
       connections[user].send("whisper from "+self.username+":"+msg)
       connections[self.username].send("whisper to "+user+":"+msg)
     else:
       self.client.send("Sorry, you cannot whisper to "+user+" because they do not exist") 

  def send_all(self, user, msg):
     #serverLogger.logger.info('All connections '+' '.join(connections.keys()))
     serverLogger.logger.info('Sending message '+msg+' to all')
     for socket in connections.values():
       socket.send(user+': '+msg)      

  def update_userlist(self):
    userlist = pickle.dumps(connections.keys()) #use the best you can pickle
    serverLogger.logger.info("Sending pickle")
    self.send_all('[SERVER]',userlist) #the user sending this is nothing

  def run(self):
    data = self.client.recv(self.size)

    try:
      requested_username = data.split(':')[1] #receive a username request
    except IndexError:
      serverLogger.logger.warn("Client did not adhere to protocol "+data)
      self.client.send('REJECT')
      self.client.close()
      return

    serverLogger.logger.info("Client requested name "+requested_username)

    if connections.has_key(requested_username):
      self.client.send('REJECT') 
      self.client.close() #close the socket
      serverLogger.logger.info("Client username "+requested_username+" rejected: already exists")
      return   
    else:
      self.client.send('ACCEPT')
      
      self.send_all('[SERVER]', requested_username + ' has connected')

      serverLogger.logger.info("Client username "+requested_username+" accepted")
      connections[requested_username]=self.client #add username and connection socket
      self.username = requested_username

      time.sleep(0.1) #test correctness 
      self.update_userlist() #update the user list on connect

    while self.running:
        try:
          data = self.client.recv(self.size)
        except socket.error:
          serverLogger.logger.warn("socket closed on receive")

        if data:
              user, msg = self.parse_message(data)
              serverLogger.logger.info('Parsed message: '+user+' '+msg)
              if user != 'all':
                  self.whisper(user, msg)
              else:
                try:
                  self.send_all(self.username,msg)  
                except socket.error:
                  serverLogger.logger.warn("Server Termination, Closing socket")
                  self.client.close()
                  self.running = 0
        else:
            del connections[self.username] #delete the user; associating socket as value will only work if done as pointer
            self.send_all('[SERVER]', self.username+' has disconnected') 
            self.client.close()
            serverLogger.logger.info(self.username+ 'has disconnected')
            self.update_userlist() #update the user list on disconnect
            serverLogger.logger.info(self.username+' has disconnected')

            self.running = 0

    serverLogger.logger.info("Thread terminating") 

if __name__ == "__main__":
  try:
    connections = {} 
    
    serverLogger = ServerLogger('server.log') 
    serverLogger.logger.info("starting server")
    s = Server(int(sys.argv[1]))
    print 'Hit any key to terminate server'
    s.run() 
  except IndexError:
    print 'Usage: python server.py <port number>'
