from serial import Serial
import OctoPrint_MeatPack.meatpack as mp
import OctoPrint_MeatPack.song_player as songplay
from threading import Thread
import time
import re
import enum
from array import array


class MPSyncedConfigFlags(enum.IntEnum):
    Enabled = 0
    NoSpaces = 1


class ThreadedSongPlayer:
    def __init__(self, serial_obj):
        self._running = False
        self._serial = serial_obj

    def terminate(self):
        self._running = False

    def is_running(self):
        return self._running

    def run(self):
        self._running = True
        # tuple -- (note len in ms, g-code)
        song = songplay.get_song_in_gcode()
        
        # sleep 3.5 seconds to allow command queue to empty
        time.sleep(3.5)

        note_len_offset_ms = -10

        for note in song:
            note_len_ms = note[0]
            note_text = note[1]

            if not self._running:
                break

            self._serial.write(note_text.encode("UTF-8"))
            sleep_per = float(note_len_ms + note_len_offset_ms) / 1000.0
            if sleep_per > 0.0:
                time.sleep(sleep_per)

        self._running = False



class PackingSerial(Serial):
    """This is the custom Serial wrapper using to send packed data to the printer. It inspects incoming data to
    detect the packer state (enabled or disabled), enables packing per the current settings of the plugin, and
    packs data to be sent in the appropriate manner.

    Author: Scott Mudge (mail@scottmudge.com)
    """

    def __init__(self, logger, **kwargs):
        mp.initialize()

        self._packing_enabled = True
        self._no_spaces = False
        self._expecting_response = False
        self._confirmed_sync = False
        self._sync_pending = False
        self._query_msg_timer = time.time()
        self._logger = logger
        self._log_transmission_stats = True
        self.play_song_on_print_complete = True
        self._print_started = False
        self._home_detected = False
        self._protocol_version = 0

        self._diagTimer = time.time()
        self._diagBytesSentActualTotal = 0
        self._diagBytesSentTotal = 0
        self._diagBytesSent = 0
        self._diagBytesSentActual = 0

        # Stats
        self._totalBytesSec = 0.0

        self.statsUpdateCallback = None
        self._already_initialized = False

        self._buffer = list()
        self._song_player = None
        self._song_player_thread = None

        self._config_sync_flags = array('B', len(MPSyncedConfigFlags) * [0])
        self._config_sync_flags_protocol_ver = array('B', len(MPSyncedConfigFlags) * [0])
        self._init_device_config_protocl_versions()
        self._reset_config_sync_state()

        super(PackingSerial, self).__init__(**kwargs)

# -------------------------------------------------------------------------------
    @property
    def packing_enabled(self):
        return self._packing_enabled

    @packing_enabled.setter
    def packing_enabled(self, value):
        # Set before anything else, to buffer data while state is synchronized.
        self._sync_pending = True
        self._packing_enabled = value
        self.query_config_state(True)

# -------------------------------------------------------------------------------
    @property
    def omit_all_spaces(self):
        return self._no_spaces

    @omit_all_spaces.setter
    def omit_all_spaces(self, value):
        # Set before anything else, to buffer data while state is synchronized.
        self._sync_pending = True
        self._no_spaces = value
        self.query_config_state(True)

# -------------------------------------------------------------------------------
    @property
    def log_transmission_stats(self):
        return self._log_transmission_stats

    @log_transmission_stats.setter
    def log_transmission_stats(self, value):
        if self._log_transmission_stats != value:
            self._log_transmission_stats = value
            self._diagBytesSent = 0
            self._diagBytesSentActual = 0
            self._diagBytesSentActualTotal = 0
            self._diagBytesSentTotal = 0
            self._diagTimer = time.time()

# -------------------------------------------------------------------------------
    def _init_device_config_protocl_versions(self):
        self._config_sync_flags_protocol_ver[MPSyncedConfigFlags.Enabled] = 0
        self._config_sync_flags_protocol_ver[MPSyncedConfigFlags.NoSpaces] = 1

# -------------------------------------------------------------------------------
    def _log(self, string):
        self._logger.info("[Serial]: {}".format(string))

# -------------------------------------------------------------------------------
    def _diagLog(self, string):
        self._logger.info("[General] {}".format(string))

# -------------------------------------------------------------------------------
    def cleanup(self):
        if self._song_player is not None:
            self._song_player.terminate()
        if self._song_player_thread is not None:
            self._song_player_thread.join()

# -------------------------------------------------------------------------------
    def _update_config_sync_state(self):
        all_synced = True
        for i in range(0, len(MPSyncedConfigFlags)):
            if self._config_sync_flags[i] == 0 and\
                    int(self._config_sync_flags_protocol_ver[i]) <= self._protocol_version:
                all_synced = False
        self._confirmed_sync = all_synced

# -------------------------------------------------------------------------------
    def _reset_config_sync_state(self):
        self._confirmed_sync = False
        for i in range(0, len(MPSyncedConfigFlags)):
            self._config_sync_flags[i] = 0

# -------------------------------------------------------------------------------
    def _stable_state(self):
        if not self._sync_pending and self._confirmed_sync:
            return True
        return False

# -------------------------------------------------------------------------------
    def readline(self, **kwargs):
        read = super(PackingSerial, self).readline(**kwargs)

        read_str = read.decode("UTF-8", errors="ignore")

        # Reset
        if "start" in read_str:
            self._reset_config_sync_state()
            self._log("System reset detected -- disabling MeatPack until sync.")
            return read

        # Keep sending queries every so often until response (timed internally)
        if not self._confirmed_sync:
            self.query_config_state()

        # Sync packing state
        # -------------------------------------------------------------------------------
        if "[MP]" in read_str:

            # Extract protocol version
            # -------------------------------------------------------------------------------
            if " PV" in read_str:
                protocol_match = re.search(" PV(\d+)", read_str)
                if protocol_match:
                    new_version = int(protocol_match.group(1))

                    if new_version != self._protocol_version:
                        self._log("Detected MeatPack protocol version V{}".format(new_version))
                    self._protocol_version = int(protocol_match.group(1))

            sync_pending_buf = self._sync_pending

            # Enable/Disable flag is available in all protocl versions
            # -------------------------------------------------------------------------------
            # If device packing is on but we want it off, do so here.
            if " ON" in read_str:
                # We don't want it enabled but it says it is
                if not self._packing_enabled:
                    self._config_sync_flags[MPSyncedConfigFlags.Enabled] = 0
                    self._sync_pending = True
                    super(PackingSerial, self).write(mp.get_command_bytes(mp.MPCommand_DisablePacking))
                    super(PackingSerial, self).flushOutput()
                    if not sync_pending_buf:
                        self._log("MeatPack enabled on device but will be set disabled. Sync'ing state.")
                    # Check again
                    self.query_config_state()
                else:
                    self._log("Config var [Enabled] synchronized (=enabled).")
                    self._config_sync_flags[MPSyncedConfigFlags.Enabled] = 1

            # If device packing is off but we want it on, do so here.
            elif " OFF" in read_str:
                # We do want it enabled, but it says it isn't
                if self._packing_enabled:
                    self._sync_pending = True
                    super(PackingSerial, self).write(mp.get_command_bytes(mp.MPCommand_EnablePacking))
                    super(PackingSerial, self).flushOutput()
                    if not sync_pending_buf:
                        self._log("MeatPack disabled on device but will be set enabled. Sync'ing state.")
                    # Check again
                    self.query_config_state()
                else:
                    self._log("Config var [Enabled] synchronized (=disabled).")
                    mp.set_no_spaces(self._no_spaces)
                    self._config_sync_flags[MPSyncedConfigFlags.Enabled] = 1

        # No-Spaces is only available in protocl version 1 and above
        # -------------------------------------------------------------------------------
            if self._protocol_version >= 1:
                # No spaces enabled
                if " NSP" in read_str:
                    # Need to disable it
                    if not self._no_spaces:
                        self._sync_pending = True
                        super(PackingSerial, self).write(mp.get_command_bytes(mp.MPCommand_DisableNoSpaces))
                        super(PackingSerial, self).flushOutput()
                        if not sync_pending_buf:
                            self._log("No-Spaces enabled on device, but will be set disabled. Sync'ing state.")
                        self.query_config_state()
                    # Otherwise we're good
                    else:
                        self._log("Config var [NoSpaces] synchronized (=enabled).")
                        self._config_sync_flags[MPSyncedConfigFlags.NoSpaces] = 1
                # No spaces disabled
                elif " ESP" in read_str:
                    # Need to enabled it
                    if self._no_spaces:
                        self._sync_pending = True
                        super(PackingSerial, self).write(mp.get_command_bytes(mp.MPCommand_EnableNoSpaces))
                        super(PackingSerial, self).flushOutput()
                        if not sync_pending_buf:
                            self._log("No-Spaces enabled on device, but will be set disabled. Sync'ing state.")
                        self.query_config_state()
                    # Otherwise we're good
                    else:
                        self._log("Config var [NoSpaces] synchronized (=disabled).")
                        mp.set_no_spaces(self._no_spaces)
                        self._config_sync_flags[MPSyncedConfigFlags.NoSpaces] = 1

            self._update_config_sync_state()
            if self._confirmed_sync:
                self._log("MeatPack configuration successfully synchronized and confirmed between host/device.")
                mp.set_no_spaces(self._no_spaces)
                self._sync_pending = False
                self._flush_buffer()
                # This flag is used to prevent a rush of query messages at first launch.
                self._already_initialized = True

            return bytes()

        return read

    # -------------------------------------------------------------------------------
    def _play_song_thread(self):
        if self._song_player is None:
            self._song_player = ThreadedSongPlayer(self)
        elif self._song_player.is_running():
            return

        if self._song_player_thread is not None:
            self._song_player_thread.join(timeout=1.0)
        self._song_player_thread = Thread(target=self._song_player.run)
        self._song_player_thread.start()

    # -------------------------------------------------------------------------------
    def get_transmission_stats(self):
        return {
            'totalBytes': self._diagBytesSentTotal,
            'packedBytes': self._diagBytesSentActualTotal,
            'totalBytesSec': self._totalBytesSec
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
            self._totalBytesSec = (self._diagBytesSent / elapsed_sec)

            if callable(self.statsUpdateCallback):
                self.statsUpdateCallback()

            self._diagBytesSent = 0
            self._diagBytesSentActual = 0

# -------------------------------------------------------------------------------
    def _flush_buffer(self):
        if self._stable_state():
            if len(self._buffer) > 0:
                for line in self._buffer:
                    super(PackingSerial, self).write(self._process_line_bytes(line))
                self._buffer *= 0

# -------------------------------------------------------------------------------
    def _process_line_bytes(self, line):
        if not self._packing_enabled:
            return line
        str_line = line.decode("UTF-8", errors="ignore")
        if self.play_song_on_print_complete:
            if "M84" in str_line:
                self._log("End of print detected, playing song...")
                self._play_song_thread()

        return mp.pack_line(str_line)

# -------------------------------------------------------------------------------
    def write(self, data):
        # If this is true, we are waiting for a response for the device state. Let's not write anything until it's
        # complete
        total_bytes = len(data)

        if not self._stable_state():
            if total_bytes > 2:
                self._buffer.append(data)
        else:
            self._flush_buffer()

            data_out = self._process_line_bytes(data)
            super(PackingSerial, self).write(data_out)
            actual_bytes = len(data_out)

            self._benchmark_write_speed(actual_bytes, total_bytes)
        return total_bytes

# -------------------------------------------------------------------------------
    def query_config_state(self, force=False):
        """Queries the packing state from the system. Sends command and awaits response"""
        if self.isOpen():

            # This is used to prevent too many query messages from going out at once
            if self._expecting_response:
                time_limit = 0.6 if self._already_initialized else 3.0
                if force:
                    time_limit = 0.25
                if time.time() - self._query_msg_timer < time_limit:
                    return

            self._query_msg_timer = time.time()
            self._reset_config_sync_state()
            super(PackingSerial, self).write(mp.get_command_bytes(mp.MPCommand_QueryConfig))
            self.flushOutput()
            self._expecting_response = True
        else:
            self._log("Cannot query packing state -- port not open.")
