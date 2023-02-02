import copy
import mido
import os


def iter_tempo(track, tempos):
    cur_tempo_idx = 0
    time = 0

    for message in track:
        time += message.time

        if cur_tempo_idx + 1 < len(tempos) and time >= tempos[cur_tempo_idx + 1][1]:
            cur_tempo_idx += 1

        yield message, tempos[cur_tempo_idx][0]


def scale_tempo(track, new_tempo, tempos):
    for message, tempo in iter_tempo(track, tempos):
        if message.type not in ('note_on', 'note_off'):
            continue

        scale_factor = new_tempo / tempo
        message.time = int(message.time * scale_factor)


def instrument_tracks(midifile):
    for track in midifile.tracks:
        for m in track:
            if m.type == 'program_change' and m.channel != 9:
                yield track
                break


C3 = 48
C5 = 72
def transpose(midifile):
    insts = list(instrument_tracks(midifile))
    max_note = max(m.note for track in insts for m in track if m.type == 'note_on')
    min_note = min(m.note for track in insts for m in track if m.type == 'note_on')
    transpose = (C3 - min_note) % 12

    print(f'Transposing by {transpose} semitones...')

    for track in insts:
        for m in track:
            if m.type not in ('note_on', 'note_off'):
                continue

            m.note += transpose

            while m.note < C3:
                m.note += 12

            while m.note > C5:
                m.note -= 12


def split_parts(midifile):
    r = [midifile.tracks[0]]

    for track in instrument_tracks(midifile):
        new_tracks = [[mido.MidiTrack(), None]]

        for m in track:
            print(m)
            if m.type == 'note_on':
                create_new_track = True

                for new_track in new_tracks:
                    if new_track[1] is None:
                        new_track[0].append(m)
                        new_track[1] = m.note
                        create_new_track = False

                if create_new_track and len(new_tracks) > 1:
                    # first look for tracks with duplicate notes we can use
                    for idx, new_track1 in enumerate(new_tracks):
                        for new_track2 in new_tracks[idx + 1:]:
                            if new_track1[1] is not None and new_track1[1] == new_track2[1]:
                                new_track2[0] = new_track2[0][:-1]
                                new_track2[1] = m.note
                                create_new_track = False


                if create_new_track:
                    new_track = copy.deepcopy(new_tracks[0])
                    new_track[0].remove(new_track[0][-1])
                    new_track[0].append(m)
                    new_track[1] = m.note
                    new_tracks.append(new_track)

            elif m.type == 'note_off':
                for new_track in new_tracks:
                    if new_track[1] == m.note:
                        new_track[0].append(m)
                        new_track[1] = None

            else:
                for new_track in new_tracks:
                    new_track[0].append(m)

        r.extend([n[0] for n in new_tracks])

    return r

def autogen(input_filename, output_filename):
    midifile = mido.MidiFile(input_filename)

    tempo_track = midifile.tracks[0]
    tempos = []
    time = 0

    for message in tempo_track:
        if message.type != 'set_tempo':
            continue

        tempo = 60000000 / message.tempo
        time += message.time
        tempos.append((tempo, time))
    
    max_tempo = max(t[0] for t in tempos)
    print(f'Adjusting to {max_tempo} bpm...')

    for track in midifile.tracks[1:]:
        scale_tempo(track, max_tempo, tempos)

    # remove tempo changes from tempo track
    to_remove = [m for m in tempo_track if m.type == 'set_tempo' and m.time > 0]
    for m in to_remove:
        tempo_track.remove(m)

    transpose(midifile)

    new_tracks = split_parts(midifile)
    midifile.tracks = new_tracks

    midifile.save(output_filename)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    parser.add_argument('-o', '--output', default=None)
    args = parser.parse_args()

    output = args.output or os.path.splitext(args.file)[0] + '.edited.mid'

    autogen(args.file, output)

if __name__ == '__main__':
    main()
