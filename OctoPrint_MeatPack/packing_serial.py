from serial import Serial
import OctoPrint_MeatPack.meatpack as mp
import OctoPrint_MeatPack.song_player as songplay
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
        self._log_transmission_stats: bool = True
        self.play_song_on_print_complete: bool = True
        self._print_started = False
        self._home_detected = False

        self._diagTimer = time.time()
        self._diagBytesSentActualTotal = 0
        self._diagBytesSentTotal = 0
        self._diagBytesSent = 0
        self._diagBytesSentActual = 0

        # Stats
        self._totalKBSent = 0.0
        self._packedKBSent = 0.0
        self._totalKBSec = 0.0

        self.statsUpdateCallback = None

        self._buffer = list()

        super().__init__(**kwargs)

# -------------------------------------------------------------------------------
    @property
    def packing_enabled(self):
        return self._packing_enabled

    @packing_enabled.setter
    def packing_enabled(self, value: bool):
        self._packing_enabled = value
        self.query_packing_state()

# -------------------------------------------------------------------------------
    @property
    def log_transmission_stats(self):
        return self._log_transmission_stats

    @log_transmission_stats.setter
    def log_transmission_stats(self, value: bool):
        if self._log_transmission_stats != value:
            self._log_transmission_stats = value
            self._diagBytesSent = 0
            self._diagBytesSentActual = 0
            self._diagBytesSentActualTotal = 0
            self._diagBytesSentTotal = 0
            self._diagTimer = time.time()

# -------------------------------------------------------------------------------
    def _log(self, string):
        self._logger.info("[Serial]: {}".format(string))

# -------------------------------------------------------------------------------
    def _diagLog(self, string):
        self._logger.info("[General] {}".format(string))

# -------------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------------
    def get_transmission_stats(self) -> dict:
        return {
            'totalKBytes': self._totalKBSent,
            'packedKBytes': self._packedKBSent,
            'totalKBSec': self._totalKBSec,
        }

        # -------------------------------------------------------------------------------
    def _benchmark_write_speed(self, bytes_sent_actual, bytes_sent_total):
        if not self._log_transmission_stats:
            return

        self._diagBytesSentActual += bytes_sent_actual
        self._diagBytesSentActualTotal += bytes_sent_actual

        self._diagBytesSent += bytes_sent_total
        self._diagBytesSentTotal += bytes_sent_total

        curTime = time.time()
        elapsed_sec = float(curTime - self._diagTimer)

        if elapsed_sec > 2.0:
            self._diagTimer = curTime

            self._totalKBSent = (self._diagBytesSentTotal / 1024.0)
            self._packedKBSent = (self._diagBytesSentActualTotal / 1024.0)
            self._totalKBSec = (self._diagBytesSent / 1024.0 / elapsed_sec)

            if callable(self.statsUpdateCallback):
                self.statsUpdateCallback()

            self._diagBytesSent = 0
            self._diagBytesSentActual = 0

# -------------------------------------------------------------------------------
    def _flush_buffer(self):
        if not self._sync_pending and self._confirmed_sync:
            if len(self._buffer) > 0:
                for line in self._buffer:
                    if self._device_packing_enabled and self._packing_enabled:
                        super().write(mp.pack_line(line.decode("UTF-8")))
                    else:
                        super().write(line)
                self._buffer.clear()

# -------------------------------------------------------------------------------
    def write(self, data):
        # If this is true, we are waiting for a response for the device state. Let's not write anything until it's
        # complete
        total_bytes = len(data)

        if not self._confirmed_sync or self._sync_pending:
            self._buffer.append(data)
        else:
            self._flush_buffer()

            use_packing = True if (self._device_packing_enabled and self._packing_enabled) else False

            data_str = data.decode("UTF-8")

            if use_packing:
                data_out = mp.pack_line(data_str)
            else:
                data_out = data

            super().write(data_out)
            actual_bytes = len(data_out)

            self._benchmark_write_speed(actual_bytes, total_bytes)

            if self.play_song_on_print_complete:
                if "M84" in data_str:
                    self._log("End of print detected, playing song...")
                    lines = songplay.get_song_in_gcode()
                    for line in lines:
                        if use_packing:
                            super().write(mp.pack_line(line))
                        else:
                            super().write(bytes(line, "UTF-8"))

            # if "G28" in data_str:
            #     self._log("Print start detected")
            #     self._print_started = True
            # if self._print_started:
            #     if "M84" in data_str:
            #         self._log("End of print detected")
            #         self._print_started = False
            #         if self.play_song_on_print_complete:
            #             self._log("Playing song...")
            #             if use_packing:
            #                 super().write(mp.pack_multiline_string(songplay.get_song_in_gcode()))
            #             else:
            #                 super().write(bytes(songplay.get_song_in_gcode(), "UTF-8"))

        return total_bytes

# -------------------------------------------------------------------------------
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
