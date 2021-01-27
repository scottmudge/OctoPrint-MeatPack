# coding=utf-8

from __future__ import absolute_import, unicode_literals
import octoprint.plugin
from octoprint.util.platform import get_os, set_close_exec
from octoprint.settings import settings
import flask
import serial
import os
from OctoPrint_MeatPack.packing_serial import PackingSerial

__author__ = "Scott Mudge <mail@scottmudge.com, https://scottmudge.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020-2021 Scott Mudge - Released under terms of the AGPLv3 License"


class MeatPackPlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.ShutdownPlugin
):
    """MeatPack plugin - provides various utilities for custom Prusa Firmware.

    Primarily, it uses a CPU-easy, fast, and effective means of G-Code compression to reduce transmission overhead
    over the serial connection.
    """

# -------------------------------------------------------------------------------
    def __init__(self):
        octoprint.plugin.SettingsPlugin.__init__(self)
        octoprint.plugin.StartupPlugin.__init__(self)
        octoprint.plugin.TemplatePlugin.__init__(self)
        octoprint.plugin.AssetPlugin.__init__(self)
        octoprint.plugin.SimpleApiPlugin.__init__(self)
        octoprint.plugin.ShutdownPlugin.__init__(self)
        self._serial_obj = None

# -------------------------------------------------------------------------------
    def serial_factory_hook(self, comm_instance, port, baudrate, read_timeout, *args, **kwargs):
        self.create_serial_obj()
        self.sync_settings_with_serial_obj()

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

        self._serial_obj.query_config_state()

        return self._serial_obj

# -------------------------------------------------------------------------------
    def sync_settings_with_serial_obj(self):
        self._serial_obj.log_transmission_stats = self._settings.get_boolean(["logTransmissionStats"])
        self._serial_obj.play_song_on_print_complete = self._settings.get_boolean(["playSongOnPrintComplete"])
        self._serial_obj.packing_enabled = self._settings.get_boolean(["enableMeatPack"])
        self._serial_obj.omit_all_spaces = self._settings.get_boolean(["omitSpaces"])

# -------------------------------------------------------------------------------
    def get_settings_defaults(self):
        return dict(
            enableMeatPack=True,
            logTransmissionStats=True,
            playSongOnPrintComplete=False,
            omitSpaces=True
        )

# -------------------------------------------------------------------------------
    def get_assets(self):
        return {
            "js": ["js/meatpack.js"],
            "clientjs": ["clientjs/meatpack.js"],
        }

# -------------------------------------------------------------------------------
    def get_settings_version(self):
        return 1

# -------------------------------------------------------------------------------
    def on_settings_migrate(self, target, current=None):
        return

# -------------------------------------------------------------------------------
    def on_shutdown(self):
        if self._serial_obj is not None:
            self._serial_obj.cleanup()

# -------------------------------------------------------------------------------
    def create_serial_obj(self):
        if not self._serial_obj:
            self._serial_obj = PackingSerial(self._logger)

            self._serial_obj.statsUpdateCallback = self.serial_obj_stats_update_callback

    def serial_obj_stats_update_callback(self):
        self._plugin_manager.send_plugin_message(self._identifier, {"message": "update"})

# -------------------------------------------------------------------------------
    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

# -------------------------------------------------------------------------------
    def on_api_get(self, request):
        return flask.jsonify(
            transmissionStats=self._serial_obj.get_transmission_stats(),
            enabled=self._serial_obj.packing_enabled
        )

# -------------------------------------------------------------------------------
    def get_version(self):
        return self._plugin_version

# -------------------------------------------------------------------------------
    def get_update_information(self):
        return dict(
            meatpack=dict(
                displayName="MeatPack - Automatic G-Code Compression",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="scottmudge",
                repo="OctoPrint-MeatPack",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/scottmudge/OctoPrint-MeatPack/archive/{target}.zip"
            )
        )

# -------------------------------------------------------------------------------
    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        cur_packing_param = self._settings.get_boolean(["enableMeatPack"])
        cur_logging_param = self._settings.get_boolean(["logTransmissionStats"])
        cur_song_param = self._settings.get_boolean(["playSongOnPrintComplete"])
        cur_nosp_param = self._settings.get_boolean(["omitSpaces"])

        if self._serial_obj.packing_enabled != cur_packing_param:
            self._logger.info("G-Code compression changed, now {}... synchronizing with device."
                              .format("Enabled" if cur_packing_param else "Disabled"))

        if self._serial_obj.log_transmission_stats != cur_logging_param:
            self._logger.info("Statistics logging setting changed: {}".format(
                "Enabled" if cur_logging_param else "Disabled"))

        if self._serial_obj.play_song_on_print_complete != cur_song_param:
            self._logger.info("Song playing setting changed: {}".format(
                "Enabled" if cur_song_param else "Disabled"))

        if self._serial_obj.omit_all_spaces != cur_nosp_param:
            self._logger.info("No whitespace setting changed: {}".format(
                "Enabled" if cur_nosp_param else "Disabled"))

        self.sync_settings_with_serial_obj()

# -------------------------------------------------------------------------------
    def on_after_startup(self):
        self.create_serial_obj()
        self.sync_settings_with_serial_obj()
        self._logger.info("MeatPack version {} loaded... current state is {}"
                          .format(self._plugin_version, "Enabled" if self._serial_obj.packing_enabled else "Disabled"))


# -------------------------------------------------------------------------------
__plugin_name__ = "MeatPack"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = MeatPackPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {"octoprint.comm.transport.serial.factory":
                            __plugin_implementation__.serial_factory_hook,
                        "octoprint.plugin.softwareupdate.check_config":
                            __plugin_implementation__.get_update_information}
