# Core MeatPack methods
# Packs a data stream, byte by byte

MeatPackLookupTbl = [
    '0',
    '1',
    '2',
    '3',
    '4',
    '5',
    '6',
    '7',
    '8',
    '9',
    '.',
    ' ',
    '\n',
    'G',
    'X',
    '\0'  # never used, 0b1111 is used to indicate next 8-bits is a full character
]

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


"""
Command Words:

0xFF (0b11111111) x 2 == Command Word

Operation: send command word (0xFF 0xFF), send command byte, send close byte (0xFF)
"""

Command_TogglePacking = 0b11111101
Command_PackingEnable = 0b11111011
Command_PackingDisable = 0b11111010
Command_ResetDeviceState = 0b11111001
Command_QueryPackingState = 0b11111000
Command_None = 0b00000000

CommandByte = 0b11111111

MeatPack_FirstUnpackable = 0b00001111
MeatPack_BothUnpackable = 0b11111111


# -------------------------------------------------------------------------------
def pack_chars(low: str, high: str) -> int:
    return int(((MeatPackReverseLookupTbl[high] & 0xF) << 4) | (MeatPackReverseLookupTbl[low] & 0xF))


# -------------------------------------------------------------------------------
def is_packable(char) -> bool:
    if char in MeatPackReverseLookupTbl:
        return True
    return False


# -------------------------------------------------------------------------------
def get_command_bytes(command) -> bytearray:
    out = bytearray()
    out.append(CommandByte)
    out.append(CommandByte)
    out.append(command)
    return out


# -------------------------------------------------------------------------------
def pack_line(line: str) -> bytearray:
    bts = bytearray()

    if line[0] == ';':
        return bts
    if line[0] == '\n':
        return bts
    if line[0] == '\r':
        return bts
    if len(line) < 2:
        return bts
    if ';' in line:
        line = line.split(';')[0].rstrip() + "\n"
    line_len = len(line)

    for line_idx in range(0, line_len, 2):
        skip_last = False
        if line_idx == (line_len - 1):
            skip_last = True

        char_1 = line[line_idx]
        if skip_last:
            char_2 = char_1
            char_1 = ' '
        else:
            char_2 = line[line_idx + 1]

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
def pack_file(in_filename: str, out_filename: str):
    in_file = open(in_filename, "r")
    out_file = open(out_filename, "wb")

    if not in_file.readable():
        raise IOError("cannot read input file")
    if not out_file.writable():
        raise IOError("cannot write to output file")

    file_data_lines = in_file.readlines()
    file_idx = 0

    bts = bytearray()

    bts.append(CommandByte)
    bts.append(CommandByte)
    bts.append(Command_PackingEnable)

    for line in file_data_lines:
        bts += pack_line(line)

    bts.append(CommandByte)
    bts.append(CommandByte)
    bts.append(Command_ResetDeviceState)

    out_file.write(bts)
    out_file.flush()


# -------------------------------------------------------------------------------
def strip_comments(in_filename: str, out_filename: str):
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