#!/usr/bin/env python3

import subprocess
from shutil import which
import logging
import logging.handlers


def send_to_matrix(message: str) -> None:
    if which("sendxmpppy") is None:
        logging.warning("Could not send error via xmpp.")
        return
    subprocess.call(["sendxmpppy", message], stdout=subprocess.DEVNULL)


class LogSenderHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.is_logging = False

    def emit(self, record):
        msg = f"[Apps tools error] {record.msg}"
        send_to_matrix(msg)

    @classmethod
    def add(cls, level=logging.ERROR):
        if not logging.getLogger().handlers:
            logging.basicConfig()

        # create handler
        handler = cls()
        handler.setLevel(level)
        # add the handler
        logging.getLogger().handlers.append(handler)


def enable():
    """Enables the LogSenderHandler"""
    LogSenderHandler.add(logging.ERROR)
