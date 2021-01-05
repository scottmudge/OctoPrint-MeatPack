# Core OctoPrint plugin for MeatPack, a real-time, CPU-easy g-code compression/packing algorithm developed by:
#
# Scott Mudge
# mail@scottmudge.com
# https://scottmudge.com/
#
# Please see my website for links to the custom Prusa Firmware builds with support for MeatPacking over Serial/SD Card
#

from __future__ import absolute_import, unicode_literals
import octoprint.plugin
from octoprint.util.platform import get_os, set_close_exec
from octoprint.settings import settings
import serial
import os
from packing_serial import PackingSerial
import logging
from setup import plugin_version


class MeatPackHookPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin):

    def __init__(self):
        super().__init__()
        self._enable_packing = True
        self._logger = logging.getLogger("MeatPack")
        self._serial_obj = None

    def serial_factory_hook(self, comm_instance, port, baudrate, read_timeout, *args, **kwargs):
        self._serial_obj = PackingSerial()
        self._serial_obj.packing_enabled = self._enable_packing

        self._serial_obj.timeout = read_timeout
        self._serial_obj.write_timeout = 0
        if baudrate == 0:
            self._serial_obj.baudrate = 115200
        else:
            self._serial_obj.baudrate = baudrate
        self._serial_obj.port = str(port)

        # Parity workaround needed for linux
        use_parity_workaround = settings().get(["serial", "useParityWorkaround"])
        needs_parity_workaround = get_os() == "linux" and os.path.exists("/etc/debian_version")  # See #673

        if use_parity_workaround == "always" or (needs_parity_workaround and use_parity_workaround == "detect"):
            self._serial_obj.parity = serial.PARITY_ODD
            self._serial_obj.open()
            self._serial_obj.close()
            self._serial_obj.parity = serial.PARITY_NONE

        self._serial_obj.open()

        # Set close_exec flag on serial handle, see #3212
        if hasattr(self._serial_obj, "fd"):
            # posix
            set_close_exec(self._serial_obj.fd)
        elif hasattr(self._serial_obj, "_port_handle"):  
            # win32
            # noinspection PyProtectedMember
            set_close_exec(self._serial_obj._port_handle)

        return self._serial_obj

    def get_settings_defaults(self):
        return dict(
            enable_meatpack=True
        )

    def on_after_startup(self):
        self._enable_packing = self._settings.get_boolean["enable_meatpack"]
        self._logger.info("MeatPack version {} loaded... current state is {}"
                          .format(plugin_version, "Enabled" if self._enable_packing else "Disabled"))

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        cur_packing_param = self._settings.get_boolean["enable_meatpack"]
        if self._enable_packing != cur_packing_param:
            self._logger.info("MeatPack changed, now {}... synchronizing with device."
                              .format("Enabled" if cur_packing_param else "Disabled"))
            self._enable_packing = cur_packing_param
            self._serial_obj.packing_enabled = self._enable_packing

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]


