#!/usr/bin/env python3

import subprocess
from shutil import which
import logging
import logging.handlers


class XmppLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.is_logging = False

    def emit(self, record):
        if which("sendxmpppy") is None:
            return

        msg = f"[Applist builder error] {record.msg}"
        subprocess.call(["sendxmpppy", msg], stdout=subprocess.DEVNULL)

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
    """Enables the XmppLogHandler"""
    XmppLogHandler.add(logging.ERROR)
