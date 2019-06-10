# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import signal
import logging
import multiprocessing
import json
from queue import Empty
from threading import Thread
from websocket_server import WebsocketServer # pip install git+https://github.com/Pithikos/python-websocket-server


class SocketServer(multiprocessing.Process):

    def __init__(self, port, commands, events = None):
        super(SocketServer, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.events = events
        self.stoprequest = multiprocessing.Event()
        self.server = WebsocketServer(port)
        self.thread = Thread(None, self.server.run_forever, "SLA Socket Server")
        self.server.set_fn_new_client(self._onNewClient)
        self.server.set_fn_client_left(self._onClientLeft)
        self.server.set_fn_message_received(self._onMessageReceived)
        self.newClientData = dict()
    #enddef


    def signalHandler(self, signum, frame):
        self.logger.debug("signal received")
        self.stoprequest.set()
    #enddef


    def join(self, timeout = None):
        self.stoprequest.set()
        super(SocketServer, self).join(timeout)
    #enddef


    def run(self):
        self.logger.debug("process started")
        self.thread.start()
        signal.signal(signal.SIGTERM, self.signalHandler)

        while not self.stoprequest.is_set():

            try:
                data = self.commands.get(timeout = 0.1)
            except Empty:
                continue
            except Exception:
                self.logger.exception("get command exception")
                continue
            #endtry

            try:
                self.server.send_message_to_all(json.dumps(self.formatMessage(data)))
            except Exception:
                self.logger.exception("send_message_to_all() exception")
                continue
            #endtry

        #endwhile

        self.logger.debug("shutting down server")
        self.server.shutdown()
        self.logger.debug("process ended")
    #enddef


    def formatMessage(self, data):
        self.logger.debug("data: '%s'", str(data))
        self.newClientData = data
        return data
    #enddef


    def receiveMessage(self, data):
        return data
    #enddef


    def _onClientLeft(self, client, server):
        try:
            if client:
                self.logger.debug("Client [%d]:%s:%d has disconnected",
                        client['id'], client['address'][0], client['address'][1])
            #endif
        except Exception:
            self.logger.exception("_onClientLeft() exception")
        #endtry
    #enddef


    def _onNewClient(self, client, server):
        try:
            if client:
                self.logger.debug("New client [%d]:%s:%d connected",
                        client['id'], client['address'][0], client['address'][1])
                self.server.send_message(client, json.dumps(self.formatMessage(self.newClientData)))
            #endif
        except Exception:
            self.logger.exception("_onNewClient() exception")
        #endtry
    #enddef


    def _onMessageReceived(self, client, server, message):
        try:
            if client:
                self.logger.debug("Message from client [%d]:%s:%d - '%s'",
                        client['id'], client['address'][0], client['address'][1], str(message))
                if self.events:
                    self.events.put(json.loads(self.receiveMessage(message)))
                else:
                    self.logger.warning("No queue for received message")
                #endif
            #endif
        except Exception:
            self.logger.exception("_onMessageReceived() exception")
        #endtry
    #enddef

#endclass

