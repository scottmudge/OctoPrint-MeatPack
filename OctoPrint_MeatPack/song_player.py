LowFreq = 988
HighFreq = 1318


def get_note_str(freq: int, length: int):
    if freq < 0:
        freq = 0
    elif freq > 20000:
        freq = 20000

    if length < 1:
        length = 1
    elif length > 5000:
        length = 50000

    return "M300 S{} P{}\n".format(freq, length)


def get_song_in_gcode():
    out = str()
    out += get_note_str(LowFreq, 83)
    out += get_note_str(HighFreq, 680)
    out += get_note_str(0, 1000)
    out += get_note_str(LowFreq, 83)
    out += get_note_str(HighFreq, 680)
    return out

