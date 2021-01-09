LowFreq = 988
HighFreq = 1318



BaseNotes = {
    "C": 32.70,
    "D": 36.71,
    "E": 41.20,
    "F": 43.65,
    "G": 49.00,
    "A": 55.00,
    "B": 61.74
}



def get_note_freq(note: str, octave: int) -> int:
    return int(round(BaseNotes[note] * (2**(octave-1))))


BPM = 140
EightNote = int(round(((60.0 / BPM) / 8.0))) * 1000
QuarterNote = int(round(EightNote * 2.0))
HalfNote = int(round(QuarterNote * 2.0))
FullNote = int(round(HalfNote * 2.0))
OctaveShift = 0



MeatBallSongNotes = (
    ("C", 4, EightNote),
    ("C", 4, EightNote),
    ("E", 4, EightNote),
    ("G", 4, EightNote),
    ("C", 5, QuarterNote),
    ("A", 4, QuarterNote),
    ("F", 4, EightNote),
    ("F", 4, EightNote),
    ("G", 4, EightNote),
    ("A", 4, EightNote),
    ("G", 4, QuarterNote),
    ("C", 4, EightNote),
    ("C", 4, EightNote),
    ("E", 4, EightNote),
    ("G", 4, EightNote),
    ("G", 4, QuarterNote),
    ("D", 4, QuarterNote),
    ("F", 4, EightNote),
    ("F", 4, EightNote),
    ("E", 4, EightNote),
    ("D", 4, EightNote),
    ("C", 4, HalfNote),
)


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

    for note in MeatBallSongNotes:
        note_str: str = note[0]
        note_oct: int = note[1]
        note_len: int = note[2]
        note_freq = get_note_freq(note_str, note_oct + OctaveShift)
        out.append(get_note_str(note_freq, note_len))
    return out

