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
        length = 5000

    return "M300 S{} P{} \n".format(str(freq), str(length))


def get_song_in_gcode() -> list:
    out = list()
    out.append(get_note_str(988, 83))
    out.append(get_note_str(1318, 680))
    out.append(get_note_str(0, 100))
    out.append(get_note_str(988, 83))
    out.append(get_note_str(1318, 680))
    return out

