from serial import Serial
import OctoPrint_MeatPack.meatpack as mp
import logging
import time


class PackingSerial(Serial):
    """This is the custom Serial wrapper using to send packed data to the printer. It inspects incoming data to
    detect the packer state (enabled or disabled), enables packing per the current settings of the plugin, and
    packs data to be sent in the appropriate manner.

    Author: Scott Mudge (mail@scottmudge.com)
    """

    def __init__(self, logger, **kwargs):
        self._packing_enabled = True
        self._expecting_response = False
        self._confirmed_sync = False
        self._device_packing_enabled = False
        self._sync_pending = False
        self._confirm_sync_timer = time.time()
        self._logger = logger

        self._diagTimer = time.time()
        self._diagBytesWritten = 0

        self._buffer = list()

        super().__init__(**kwargs)

    @property
    def packing_enabled(self):
        return self._packing_enabled

    @packing_enabled.setter
    def packing_enabled(self, value: bool):
        self._packing_enabled = value
        self.query_packing_state()

    def _log(self, string):
        self._logger.info("[Serial]: {}".format(string))

    def _diagLog(self, string):
        self._logger.info("[General] {}".format(string))

    def readline(self, **kwargs) -> bytes:
        read = super().readline(**kwargs)

        str = read.decode("UTF-8")

        # Reset
        if "start" in str:
            self._confirmed_sync = False
            self._log("System reset detected -- disabling meatpack until sync.")
            return read

        if not self._confirmed_sync:
            self.query_packing_state()

        # Sync packing state
        if "[MP]" in str:

            # If device packing is on but we want it off, do so here.
            if " ON" in str:
                if not self._packing_enabled:
                    self._sync_pending = True
                    super().write(mp.get_command_bytes(mp.Command_PackingDisable))
                    super().flushOutput()
                    self._log("MeatPack enabled on device but set to be disabled. Sync'ing state...")
                    # Check again
                    self.query_packing_state()
                else:
                    self._log("MeatPack state synchronized - ENABLED")
                    self._device_packing_enabled = True
                    self._sync_pending = False
                    self._confirmed_sync = True
                    self._flush_buffer()

            # If device packing is off but we want it on, do so here.
            elif " OFF" in str:
                if self._packing_enabled:
                    self._sync_pending = True
                    super().write(mp.get_command_bytes(mp.Command_PackingEnable))
                    super().flushOutput()
                    self._log("MeatPack disabled on device but set to be enabled. Sync'ing state...")
                    # Check again
                    self.query_packing_state()
                else:
                    self._log("MeatPack state synchronized - DISABLED")
                    self._confirmed_sync = True
                    self._sync_pending = False
                    self._device_packing_enabled = False
                    self._flush_buffer()

            return bytes()

        return read

    def _benchmark_write_speed(self, bytes_written):
        self._diagBytesWritten += bytes_written

        curTime = time.time()
        elapsed_sec = float(curTime - self._diagTimer)
        if elapsed_sec > 10.0:
            self._diagTimer = curTime
            self._diagLog("Avg bytes per second sent: {}".format(float(self._diagBytesWritten) / elapsed_sec))
            self._diagBytesWritten = 0

    def _flush_buffer(self):
        if not self._sync_pending and self._confirmed_sync:
            if len(self._buffer) > 0:
                for line in self._buffer:
                    if self._confirmed_sync and  self._device_packing_enabled and self._packing_enabled:
                        super().write(mp.pack_line(line.decode("UTF-8")))
                    else:
                        super().write(line)
                self._buffer.clear()

    def write(self, data):
        # If this is true, we are waiting for a response for the device state. Let's not write anything until it's
        # complete
        if not self._confirmed_sync or self._sync_pending:
            self._buffer.append(data)
        else:
            self._flush_buffer()

            if self._device_packing_enabled and self._packing_enabled:
                super().write(mp.pack_line(data.decode("UTF-8")))
            else:
                super().write(data)

        bytes_written = len(data)
        self._benchmark_write_speed(bytes_written)

        return bytes_written

    def enable_packing(self):
        if not self._packing_enabled:
            pass

    def query_packing_state(self):
        """Queries the packing state from the system. Sends command and awaits response"""
        if self.isOpen():
            if self._expecting_response:
                if time.time() - self._confirm_sync_timer < 3.0:
                    return
            self._confirm_sync_timer = time.time()
            self._confirmed_sync = False
            super().write(mp.get_command_bytes(mp.Command_QueryPackingState))
            self.flushOutput()
            self._expecting_response = True
        else:
            self._log("Cannot query packing state -- port not open.")

