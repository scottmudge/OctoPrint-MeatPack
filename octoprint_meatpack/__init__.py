from meatpack_plugin import MeatPackHookPlugin

__plugin_pythoncompat__ = ">=3.7"
__plugin_name__ = "MeatPack GCode Compression"


def __plugin_load__():
    plugin = MeatPackHookPlugin()

    global __plugin_implementation__
    __plugin_implementation__ = plugin

    global __plugin_hooks__
    __plugin_hooks__ = {"octoprint.comm.transport.serial.factory": plugin.serial_factory_hook}
