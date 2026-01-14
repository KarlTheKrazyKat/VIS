#In 8:45

from loguru import logger
import subprocess
import shlex

from notifypy.exceptions import BinaryNotFound
from notifypy.os_notifiers._base import BaseNotifier
from shutil import which
NOTIFY = which('notify-send') # alternatively: from ctypes.util import find_library 
APLAY = which('aplay')


class LinuxNotifierLibNotify(BaseNotifier):
    def __init__(self, **kwargs):
        """Main Linux Notification Class

        This uses libnotify's tool of notfiy-send.
        """
        pass

    def send_notification(
        self,
        notification_title=None,
        notification_subtitle=None,
        **kwargs,
    ):
        try:
            notification_title = " " if notification_title == "" else notification_title
            notification_subtitle = (
                " " if notification_subtitle == "" else notification_subtitle
            )

            generated_command = [
                NOTIFY,
                notification_title,
                notification_subtitle,
            ]

            if kwargs.get("notification_icon"):
                generated_command.append(f"--icon={shlex.quote(kwargs.get('notification_icon'))}")

            if kwargs.get("application_name"):
                generated_command.append(
                    f"--app-name={shlex.quote(kwargs.get('application_name'))}"
                )

            if kwargs.get('notification_urgency'):
                generated_command.extend(["-u", kwargs.get('notification_urgency')])

            logger.debug(f"Generated command: {generated_command}")
            if kwargs.get("notification_audio"):

                if APLAY == None:
                    raise BinaryNotFound("aplay (Alsa)")

                subprocess.Popen(
                    [APLAY, kwargs.get("notification_audio")],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                )

            subprocess.check_output(generated_command)
            return True
        except subprocess.CalledProcessError:
            logger.exception("Unable to send notification.")
            return False
        except Exception:
            logger.exception("Unhandled exception for sending notification.")
            return False

LinuxNotifierLibNotify().send_notification("PYWOM","AssetManager")

#Turn this into VIS notifier by Copying BaseNotifier into VIS
#Check License out to verify this is alright