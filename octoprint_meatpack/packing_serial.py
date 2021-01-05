from serial import Serial
import meatpack as mp
import logging


class PackingSerial(Serial):
    """
    This is the custom Serial wrapper using to send packed data to the printer. It inspects incoming data to
    detect the packer state (enabled or disabled), enables packing per the current settings of the plugin, and
    packs data to be sent in the appropriate manner.

    Author: Scott Mudge (mail@scottmudge.com)
    """

    def __init__(self, **kwargs):
        self._packing_enabled = True
        self._expecting_response = False
        self._confirmed_sync = False
        self._logger = logging.getLogger(__name__)

        super().__init__(**kwargs)

    @property
    def packing_enabled(self):
        return self._packing_enabled

    @packing_enabled.setter
    def packing_enabled(self, value: bool):
        self._packing_enabled = value
        self._query_packing_state()


    def readline(self, **kwargs) -> bytes:
        read = super().readline(**kwargs)

        # Look for response to command
        if self._expecting_response:
            self._expecting_response = False

            # Sync packing state
            str = read.decode("UTF-8")
            if "[MP]" in str:

                # If device packing is on but we want it off, do so here.
                if " ON" in str:
                    if not self._packing_enabled:
                        self.write(mp.get_command_bytes(mp.Command_PackingDisable))
                        self.flushOutput()
                        self._logger.warning("MeatPack enabled on device but set to be disabled. Sync'ing state...")
                        # Check again
                        self._query_packing_state()
                    else:
                        self._confirmed_sync = True

                # If device packing is off but we want it on, do so here.
                elif " OFF" in str:
                    if self._packing_enabled:
                        self.write(mp.get_command_bytes(mp.Command_PackingEnable))
                        self.flushOutput()
                        self._logger.warning("MeatPack disabled on device but set to be enabled. Sync'ing state...")
                        # Check again
                        self._query_packing_state()
                    else:
                        self._confirmed_sync = True

        return read

    def write(self, data):

        # TODO -- Add Packing Here
        if not self._confirmed_sync:
            # TODO -- Buffer data here
            pass

        return super().write(data)


    def enable_packing(self):
        if not self._packing_enabled:
            pass

    def _query_packing_state(self):
        """Queries the packing state from the system. Sends command and awaits response"""
        if self.isOpen():
            self._confirmed_sync = False
            self.write(mp.get_command_bytes(mp.Command_QueryPackingState))
            self.flushOutput()
            self._expecting_response = True
