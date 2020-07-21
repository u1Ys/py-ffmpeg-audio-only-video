#!/usr/bin/env python3

import fileinput
import os
import re
import tempfile

from perlcompat import getopts

FADE = True
FADE_MARGIN_SEC = 5


def crop_audio(audiofilename, begin, duration, outputname):
    os.system(f'ffmpeg -ss {begin} -t {duration} -y -i {audiofilename} -c copy {outputname}')
    return outputname


def concat_audio(audiofilenames, outputname, fade_effect=False):
    if len(audiofilenames) == 1:
        os.system(f'mv {audiofilenames[0]} {outputname}')
        return outputname
    if fade_effect:
        _concat_audio_with_fade(audiofilenames, outputname)
    else:
        os.system('ffmpeg -i "concat:{}" -y -c copy {}'.format(
            '|'.join(audiofilenames), outputname
        ))
    return outputname


def _concat_audio_with_fade(audiofilenames, outputname):
    # acrossfade only allows two joins, so join recursively audiofilenames
    if len(audiofilenames) > 2:
        _recursive_concat_audios_fade(audiofilenames, outputname)
        return
    # ref: https://nico-lab.net/audio_crossfade_with_ffmpeg/
    os.system('ffmpeg -i {} -filter_complex "acrossfade=duration={}:overlap=false" -y {}'.format(
        ' -i '.join(audiofilenames), FADE_MARGIN_SEC, outputname
    ))


def _recursive_concat_audios_fade(audiofilenames, outputname):
    tmp_in = open(audiofilenames.pop(0))
    while audiofilenames:
        tmp_out = tempfile.NamedTemporaryFile(suffix='.wav')
        concat_audio([tmp_in.name, audiofilenames.pop(0)], tmp_out.name, fade_effect=True)
        tmp_in.close()
        tmp_in = tmp_out

    os.system(f'cp {tmp_out.name} {outputname}')
    return outputname


def create_video(imagefilename, audiofilename, outputname):
    os.system(f'''ffmpeg -loop 1 -i {imagefilename} -i {audiofilename} \
-c:v libx264 -c:a aac -b:a 192k -shortest -y \
{outputname}''')


def parse_script_file(fade=False):
    # {filename (str): [(begin_sec (int), duration_sec (int)),
    #                   (begin_sec (int), duration_sec (int)), ...]}
    crop_info = {}
    for line in fileinput.input():
        line = line.rstrip()
        # skip comment line
        if re.search(r'^\s+#', line):
            continue
        # case of file name line
        m = re.search(r'\- (.*)', line)
        if m:
            filename = m.group(1)
            crop_info[filename] = []
            continue
        # case of time-specific line
        m = re.search(r'(\d+):(\d+)-(\d+):(\d+)', line)
        if m:
            begin = int(m.group(1)) * 60 + int(m.group(2))
            if fade:
                begin = max(0, begin - FADE_MARGIN_SEC)
            duratoin = int(m.group(3)) * 60 + int(m.group(4)) - begin
            if fade:
                duratoin += FADE_MARGIN_SEC
            crop_info[filename].append((begin, duratoin))
            continue
    return crop_info


def create_audio(outputname, workdir):
    tempfiles = []

    def _create_tempfile():
        tempfiles.append(tempfile.NamedTemporaryFile(suffix='.wav', dir=workdir))
        return tempfiles[-1].name

    def _close_tempfiles():
        [fp.close() for fp in tempfiles if os.path.exists(fp.name)]

    crop_info = parse_script_file(fade=FADE)

    volumes = []
    for filename, durations in crop_info.items():
        volume_name = _create_tempfile()
        concat_audio([crop_audio(filename, begin, duration, _create_tempfile())
                      for begin, duration in durations],
                     volume_name, fade_effect=FADE)
        volumes.append(volume_name)
    concat_audio(volumes, outputname, fade_effect=FADE)

    _close_tempfiles()
    return outputname


def main():
    opts = getopts('a:i:o:')
    output = opts.o if opts.o else 'output.mp4'
    imagefile = opts.i if opts.i else 'src/background.png'

    with tempfile.TemporaryDirectory() as workdir:
        audiofile = opts.a if opts.a else \
            tempfile.NamedTemporaryFile(suffix='.wav', dir=workdir).name
        create_audio(audiofile, workdir=workdir)
        create_video(imagefile, audiofile, output)


if __name__ == "__main__":
    main()
