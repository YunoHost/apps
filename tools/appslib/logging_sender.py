#!/usr/bin/env python3

import subprocess
import logging
import logging.handlers


def notify(message: str, channel: str, markdown: bool = False) -> None:
    print(f"{channel} -> {message}")

    chan_list = ["dev", "apps", "doc"]

    if not any(channel in x for x in chan_list):
        logging.error(
            f"Provided chan '{channel}' is not part of the available options ('dev', 'apps', 'doc')."
        )

    for char in ["'", "`", "!", ";", "$"]:
        message = message.replace(char, "")

    command = [
        "/var/www/webhooks/matrix-commander",
        "--message",
        message,
        "--credentials",
        "/var/www/webhooks/credentials.json",
        "--store",
        "/var/www/webhooks/store",
        "--room",
        f"yunohost-{channel}",
    ]
    if markdown:
        command.append("--markdown")

    try:
        subprocess.call(command, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        logging.warning(
            f"""Could not send a notification on {channel}.
            Message: {message}
            Error: {e}"""
        )


class LogSenderHandler(logging.Handler):
    def __init__(self) -> None:
        logging.Handler.__init__(self)
        self.is_logging = False

    def emit(self, record: logging.LogRecord) -> None:
        msg = f"[Apps tools error] {record.msg}"
        notify(msg, "dev")

    @classmethod
    def add(cls, level: int = logging.ERROR) -> None:
        if not logging.getLogger().handlers:
            logging.basicConfig()

        # create handler
        handler = cls()
        handler.setLevel(level)
        # add the handler
        logging.getLogger().handlers.append(handler)


def enable() -> None:
    """Enables the LogSenderHandler"""
    LogSenderHandler.add(logging.ERROR)
