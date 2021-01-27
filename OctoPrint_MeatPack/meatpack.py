# Core MeatPack methods
# Packs a data stream, byte by byte
from array import array

# For faster lookup and access
MeatPackLookupTablePackable = array('B', 256 * [0])
MeatPackLookupTableValue = array('B', 256 * [0])

MeatPackSpaceReplacedCharacter = 'E'
MeatPackOmitWhitespaces = False

MeatPackReverseLookupTbl = {
    '0': 0b00000000,
    '1': 0b00000001,
    '2': 0b00000010,
    '3': 0b00000011,
    '4': 0b00000100,
    '5': 0b00000101,
    '6': 0b00000110,
    '7': 0b00000111,
    '8': 0b00001000,
    '9': 0b00001001,
    '.': 0b00001010,
    ' ': 0b00001011,
    '\n': 0b00001100,
    'G': 0b00001101,
    'X': 0b00001110,
    '\0': 0b00001111  # never used, 0b1111 is used to indicate next 8-bits is a full character
}


ArraysInitialized = False


def initialize_arrays():
    global ArraysInitialized
    global MeatPackLookupTablePackable
    global MeatPackLookupTableValue

    if not ArraysInitialized:
        for i in range (0, 255):
            MeatPackLookupTablePackable[i] = MeatPackLookupTableValue[i] = 0
    
        for char, value in MeatPackReverseLookupTbl.items():
            c = ord(char)
            MeatPackLookupTablePackable[c] = 1
            MeatPackLookupTableValue[c] = value

        ArraysInitialized = True


"""
Command Words:

0xFF (0b11111111) x 2 == Command Word

Operation: send command word (0xFF 0xFF), send command byte, send close byte (0xFF)
"""

MPCommand_None              = 0
# MPCommand_TogglePacking     = 253 -- Currently unused, byte 253 can be reused later.
MPCommand_EnablePacking     = 251
MPCommand_DisablePacking    = 250
MPCommand_ResetAll          = 249
MPCommand_QueryConfig       = 248
MPCommand_EnableNoSpaces    = 247
MPCommand_DisableNoSpaces   = 246
MPCommand_SignalByte        = 0xFF


MeatPack_BothUnpackable = 0b11111111


# -------------------------------------------------------------------------------
def initialize():
    initialize_arrays()


# -------------------------------------------------------------------------------
def pack_chars(low, high):
    return int(((MeatPackLookupTableValue[ord(high)] & 0xF) << 4) | (MeatPackLookupTableValue[ord(low)] & 0xF))


# -------------------------------------------------------------------------------
def is_packable(char):
    return False if MeatPackLookupTablePackable[ord(char)] == 0 else True


# -------------------------------------------------------------------------------
def set_no_spaces(no_spaces):
    global MeatPackOmitWhitespaces
    global MeatPackLookupTablePackable
    global MeatPackLookupTableValue

    MeatPackOmitWhitespaces = no_spaces
    if no_spaces:
        MeatPackLookupTableValue[ord(MeatPackSpaceReplacedCharacter)] = MeatPackReverseLookupTbl.get(' ')
        MeatPackLookupTablePackable[ord(MeatPackSpaceReplacedCharacter)] = 1
        MeatPackLookupTablePackable[ord(' ')] = 0
    else:
        MeatPackLookupTablePackable[ord(MeatPackSpaceReplacedCharacter)] = 0
        MeatPackLookupTablePackable[ord(' ')] = 1


# -------------------------------------------------------------------------------
def get_command_bytes(command):
    out = bytearray()
    out.append(MPCommand_SignalByte)
    out.append(MPCommand_SignalByte)
    out.append(command)
    return out


# -------------------------------------------------------------------------------
def _unified_method(line):
    # If it's an "G" command, then remove whitespace.
    m_idx = line.find('G')
    if m_idx >= 0:

        # Check to see if the G is at the end of the line
        if m_idx + 1 >= len(line):
            return line

        # check to see if the "G" has a number after.
        if 48 <= ord(line[m_idx + 1]) <= 57:
            # Fix case capitalization for relevant letters (only packable ones)
            # It's faster to chain them together like this then make a
            # separate assignment/call to replace.
            if MeatPackOmitWhitespaces:
                line = line.replace('e', 'E').replace('x', 'X').replace('g', 'G')
            else:
                line = line.replace('x', 'X').replace('g', 'G')

            # Strip whitespace
            stripped = line.replace(' ', '')

            # Check for asterisk, meaning there is a checksum we need to recompute after
            # stripping whitespace out
            if '*' in line:
                checksum = 0
                stripped = stripped.partition('*')[0]
                for i, v in enumerate(stripped):
                    checksum ^= ord(v)
                return stripped + "*" + str(checksum) + "\n"
            return stripped
    # otherwise return line
    return line


# -------------------------------------------------------------------------------
def pack_line(line, logger=None):
    bts = bytearray()

    if line[0] == ';':
        return bts
    elif line[0] == '\n':
        return bts
    elif line[0] == '\r':
        return bts
    elif len(line) < 2:
        return bts
    elif ';' in line:
        line = line.partition(';')[0].rstrip() + "\n"

    line = _unified_method(line)

    if logger:
        logger.info("[Test] Line sent: {}".format(line))

    line_len = len(line)

    for line_idx in range(0, line_len, 2):
        skip_last = False
        if line_idx == (line_len - 1):
            skip_last = True

        char_1 = line[line_idx]

        # If we are at the last character and it needs to be skipped,
        # pack a benign character like \n into it.
        char_2 = '\n' if skip_last else line[line_idx + 1]

        c1_p = is_packable(char_1)
        c2_p = is_packable(char_2)

        if c1_p:
            if c2_p:
                bts.append(pack_chars(char_1, char_2))
            else:
                bts.append(pack_chars(char_1, "\0"))
                bts.append(ord(char_2))
        else:
            if c2_p:
                bts.append(pack_chars("\0", char_2))
                bts.append(ord(char_1))
            else:
                bts.append(MeatPack_BothUnpackable)
                bts.append(ord(char_1))
                bts.append(ord(char_2))

    return bts


# -------------------------------------------------------------------------------
def pack_file(in_filename, out_filename):
    in_file = open(in_filename, "r")
    out_file = open(out_filename, "wb")

    if not in_file.readable():
        raise IOError("cannot read input file")
    if not out_file.writable():
        raise IOError("cannot write to output file")

    file_data_lines = in_file.readlines()
    file_idx = 0

    bts = bytearray()

    bts.append(MPCommand_SignalByte)
    bts.append(MPCommand_SignalByte)
    bts.append(MPCommand_EnablePacking)

    for line in file_data_lines:
        bts += pack_line(line)

    bts.append(MPCommand_SignalByte)
    bts.append(MPCommand_SignalByte)
    bts.append(MPCommand_ResetAll)

    out_file.write(bts)
    out_file.flush()


# -------------------------------------------------------------------------------
def strip_comments(in_filename, out_filename):
    in_file = open(in_filename, "r")
    out_file = open(out_filename, "wb")

    if not in_file.readable():
        raise IOError("cannot read input file")
    if not out_file.writable():
        raise IOError("cannot write to output file")

    file_data_lines = in_file.readlines()

    for line in file_data_lines:
        if line[0] == ';':
            continue
        if line[0] == '\n':
            continue
        if line[0] == '\r':
            continue
        if len(line) < 2:
            continue
        if ';' in line:
            line = line.split(';')[0].rstrip() + "\n"
        out_file.write(line.encode("UTF-8"))
