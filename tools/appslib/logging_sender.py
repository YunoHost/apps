#!/usr/bin/env python3

import subprocess
import logging
import logging.handlers


def notify(message, channel):
    print(f"{channel} -> {message}")

    chan_list = ["dev", "apps", "doc"]

    if not any(channel in x for x in chan_list):
        logging.error(
            f"Provided chan '{channel}' is not part of the available options ('dev', 'apps', 'doc')."
        )

    for char in ["'", "`", "!", ";", "$"]:
        message = message.replace(char, "")

    try:
        subprocess.call([
                "/var/www/webhooks/matrix-commander",
                "--markdown", 
                "-m", message, 
                "-c", "/var/www/webhooks/credentials.json", 
                "--store", "/var/www/webhooks/store",
                "--room", f"yunohost-{channel}",
            ],
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        logging.warning(
            f"""Could not send a notification on {channel}.
            Message: {message}
            Error: {e}"""
        )


class LogSenderHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.is_logging = False

    def emit(self, record):
        msg = f"[Apps tools error] {record.msg}"
        notify(msg, "dev")

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
