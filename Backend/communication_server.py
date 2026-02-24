import zmq
import signal
import logging
import threading

logger = logging.getLogger("cobot_backend")

class ServerZeroMQ:
    def __init__(self, bind_address):
        self.bind_address = bind_address
        self.handler = MessageHandler()
        self._stop_event = threading.Event()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(bind_address)
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self._thread = None

    def start(self):
        """Launch server thread and block main thread (keeps signals alive)."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Server thread started")

        self._thread.join()  # main thread stays alive → signals work

    def stop(self):
        """Programmatic shutdown — callable from any thread."""
        logger.info("Stop requested")
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _handle_signal(self, sig, frame):
        logger.info("Signal %s received, shutting down", sig)
        self._stop_event.set()

    def _run(self):
        """Actual server loop — runs in background thread."""
        logger.info("Server ready and listening on %s", self.bind_address)
        try:
            while not self._stop_event.is_set():
                socks = dict(self.poller.poll(timeout=1000))
                if socks.get(self.socket) == zmq.POLLIN:
                    message = self.socket.recv_json()
                    logger.info("Message received")
                    response = self.handler.process_message(message=message)
                    self.socket.send_json(response)
                    logger.info("Response sent")
        except Exception as e:
            logger.error("Error in server loop: %s", e)
        finally:
            self._close()

    def _close(self):
        logger.info("Shutting down server")
        self.socket.close()
        self.context.term()
