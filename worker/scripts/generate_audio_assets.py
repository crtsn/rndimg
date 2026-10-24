#!/usr/bin/env python3

import argparse
import base64
import json
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "worker" / "src" / "audio_assets.json"
LETTER_SOUNDS = {
    "a": "ah", "b": "buh", "c": "kuh", "d": "duh", "e": "eh", "f": "fff",
    "g": "guh", "h": "huh", "i": "ih", "j": "juh", "k": "kuh", "l": "lll",
    "m": "mmm", "n": "nnn", "o": "oh", "p": "puh", "q": "kwuh", "r": "rrr",
    "s": "sss", "t": "tuh", "u": "uh", "v": "vuh", "w": "wuh", "x": "kss",
    "y": "yuh", "z": "zzz",
}
GRAPHEME_SOUNDS = {
    "tion": "shun", "sion": "zhun", "ough": "uff",
    "tch": "chuh", "dge": "juh", "igh": "eye", "ing": "ing", "ous": "us",
    "sch": "skuh", "thr": "thruh", "str": "struh",
    "th": "thuh", "sh": "shh", "ch": "chuh", "ph": "fff", "wh": "wuh",
    "ng": "ing", "qu": "kwuh", "ck": "kuh", "ee": "ee", "oo": "oo",
    "ea": "ee", "ai": "ay", "ay": "ay", "oa": "oh", "ow": "ow",
    "ou": "ow", "oi": "oy", "oy": "oy", "er": "err", "ar": "ar",
    "or": "or", "ir": "err", "ur": "err", "au": "aw", "aw": "aw",
    "ie": "eye",
}
PHONEME_SOUNDS = {
    "#AA": "ah", "#AE": "aah", "#AH": "uh", "#AO": "aw", "#AW": "ow",
    "#AY": "eye", "#B": "buh", "#CH": "chuh", "#D": "duh", "#DH": "thuh",
    "#EH": "eh", "#ER": "err", "#EY": "ay", "#F": "fff", "#G": "guh",
    "#HH": "huh", "#IH": "ih", "#IY": "ee", "#JH": "juh", "#K": "kuh",
    "#L": "lll", "#M": "mmm", "#N": "nnn", "#NG": "ing", "#OW": "oh",
    "#OY": "oy", "#P": "puh", "#R": "rrr", "#S": "sss", "#SH": "shh",
    "#T": "tuh", "#TH": "thuh", "#UH": "uuh", "#UW": "oo", "#V": "vuh",
    "#W": "wuh", "#Y": "yuh", "#Z": "zzz", "#ZH": "zhh",
}
COMMON_WORDS = """
a about above absolute absolutely after again against all am an and any appear are around as ask baby
at away back bad be because become been before begin being below between big both bring
build but buy by call can care carrot case chance change child children choding coding come common company consider
continue could create cut day did die different do does done down each early eat end enough
eight eighteen eleven even ever every expect fact fall family far father feel few fifteen find first five follow for forty four fourteen from
fuck further get give go good got granddaughter grandma grandmother grandpa grandfather grandson great group grow had
hand happen has have he hear hello help her here high him his how however husband i if important
in include into is it its just keep kill know large last later lead
learn leave less let life like little live long look made make man many may maybe me mean meet
member might mom mommy more most mother move much must my myself need nephew never new next niece nine nineteen no nor
not nothing now number of
off offer old on once one only open or other our out over own part pay people place play point
problem provide public put question rather read really remain remember response right run said
same say says see seem send serve set seven seventeen seventy she shit should show shut sibling silence since sister six sixteen sixty
small so some son something speak spend spouse stand start stay still stop such take talk tell ten than
that the their them then there these they thing think this thirteen thirty three those though thought through
time to too try twelve twenty turn two uncle under understand until up urmom use very wait walk want was watch
way we well went were what when where which while who why wife will win with without woman word
work world would write year yes yet you young your zero
aboba ass aunt brother conscious cousin dad daddy daughter eighty fifty gay one parent parents shining ninety
""".split()
WORD_SOUNDS = {f"@{word}": word for word in COMMON_WORDS}
WORD_SOUNDS["@aboba"] = "ah boh bah"
WORD_SOUNDS["@urmom"] = "your mom"
if Image is not None:
    Image.MAX_IMAGE_PIXELS = 255872016


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


def encode_sound(key, pronunciation, directory, silence_frames=0):
    filename = key.replace("@", "word-")
    wav_path = directory / f"{filename}.wav"
    caf_path = directory / f"{filename}.caf"

    if key == "space":
        with wave.open(str(wav_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(b"\0\0" * silence_frames)
    else:
        aiff_path = directory / f"{filename}.aiff"
        run("say", "-v", "Zarvox", "-r", "280", "-o", str(aiff_path), pronunciation)
        run("afconvert", "-f", "WAVE", "-d", "LEI16@48000", "-c", "1", str(aiff_path), str(wav_path))

    run("afconvert", "-f", "caff", "-d", "opus", "-b", "24000", "-c", "1", str(wav_path), str(caf_path))
    return parse_caf(caf_path.read_bytes())


def parse_caf(data):
    if data[:4] != b"caff":
        raise ValueError("Not a CAF file")

    chunks = {}
    offset = 8
    while offset < len(data):
        chunk_type = data[offset:offset + 4]
        size = struct.unpack_from(">q", data, offset + 4)[0]
        offset += 12
        chunks[chunk_type] = data[offset:offset + size]
        offset += size

    packet_table = chunks[b"pakt"]
    packet_count = struct.unpack_from(">q", packet_table, 0)[0]
    sizes = []
    offset = 24
    for _ in range(packet_count):
        size = 0
        while True:
            byte = packet_table[offset]
            offset += 1
            size = (size << 7) | (byte & 0x7f)
            if byte & 0x80 == 0:
                break
        sizes.append(size)

    audio = chunks[b"data"][4:]
    if sum(sizes) != len(audio):
        raise ValueError("CAF packet table does not match audio data")

    return {
        "data": base64.b64encode(audio).decode("ascii"),
        "sizes": sizes,
    }


def generate_carrot_frame(directory):
    atlas = Image.open(ROOT / "sheet_twitter_256_indexed_256.png").convert("RGBA")
    carrot = crop_emoji(atlas, 44, 6)
    carrot.thumbnail((360, 360), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (512, 512), "#18191c")
    x = (canvas.width - carrot.width) // 2
    y = (canvas.height - carrot.height) // 2
    canvas.paste(carrot, (x, y), carrot)

    eye = crop_emoji(atlas, 12, 4)
    eye.thumbnail((84, 84), Image.Resampling.LANCZOS)
    lips = crop_emoji(atlas, 12, 17)
    lips.thumbnail((96, 96), Image.Resampling.LANCZOS)

    paste_centered(canvas, eye, 205, 235)
    paste_centered(canvas, eye, 307, 235)
    paste_centered(canvas, lips, 256, 315)

    webp_path = directory / "carrot.webp"
    canvas.save(webp_path, "WEBP", quality=90, method=6)
    return extract_vp8_frame(webp_path.read_bytes())


def crop_emoji(atlas, sheet_x, sheet_y):
    left = sheet_x * 258 + 1
    top = sheet_y * 258 + 1
    emoji = atlas.crop((left, top, left + 256, top + 256))
    return emoji.crop(emoji.getbbox())


def paste_centered(canvas, emoji, center_x, center_y):
    position = (center_x - emoji.width // 2, center_y - emoji.height // 2)
    canvas.paste(emoji, position, emoji)


def extract_vp8_frame(webp):
    if webp[:4] != b"RIFF" or webp[8:12] != b"WEBP":
        raise ValueError("Not a WebP file")

    offset = 12
    while offset < len(webp):
        chunk_type = webp[offset:offset + 4]
        size = struct.unpack_from("<I", webp, offset + 4)[0]
        offset += 8
        payload = webp[offset:offset + size]
        if chunk_type == b"VP8 ":
            return base64.b64encode(payload).decode("ascii")
        offset += size + (size & 1)

    raise ValueError("WebP file does not contain a VP8 frame")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--words", nargs="+", help="regenerate only these whole-word clips")
    parser.add_argument("--phonemes", action="store_true", help="regenerate only phoneme clips")
    arguments = parser.parse_args()

    if arguments.words or arguments.phonemes:
        assets = json.loads(OUTPUT.read_text())
        keys = [f"@{word.lower()}" for word in arguments.words or []]
        unknown = [key[1:] for key in keys if key not in WORD_SOUNDS]
        if unknown:
            parser.error(f"unknown words: {', '.join(unknown)}")
        sounds = {key: WORD_SOUNDS[key] for key in keys}
        if arguments.phonemes:
            sounds.update(PHONEME_SOUNDS)

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for key, pronunciation in sounds.items():
                assets["audio"][key] = encode_sound(key, pronunciation, directory)

        OUTPUT.write_text(json.dumps(assets, separators=(",", ":")) + "\n")
        return

    existing_video = None
    if Image is None and OUTPUT.exists():
        existing_video = json.loads(OUTPUT.read_text())["video"]

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        pronunciations = LETTER_SOUNDS | GRAPHEME_SOUNDS | PHONEME_SOUNDS | WORD_SOUNDS
        audio = {
            key: encode_sound(key, pronunciation, directory)
            for key, pronunciation in pronunciations.items()
        }
        average_packets = round(
            sum(len(audio[letter]["sizes"]) for letter in LETTER_SOUNDS) / len(LETTER_SOUNDS)
        )
        audio[" "] = encode_sound("space", "", directory, (average_packets - 1) * 960)
        assets = {
            "video": existing_video or generate_carrot_frame(directory),
            "audio": audio,
        }

    OUTPUT.write_text(json.dumps(assets, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
