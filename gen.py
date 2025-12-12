#!/bin/env python3

import random
import string
import json
import PIL
import hashlib
import sys

from PIL import Image, ImageDraw, ImageFont
from random import randint
from enum import Enum

words = ["HELLO", "Hello", "Young", "Stranger", "ABSOLUTE", "CODING", "TSODING", "DEEZ", "NUTS", "URMOM"]
img_side=800
obj_limit = 15

f = open("emoji_pretty.json")
emoji_data = json.load(f)
f.close()

f = open("emotes.json")
emote_data = json.load(f)
f.close()

PIL.Image.MAX_IMAGE_PIXELS = 255872016
emoji_atlas = Image.open("sheet_twitter_256_indexed_256.png")
emote_atlas = Image.open("emotes.png")

class Object(Enum):
    image = 1
    text = 2
    char = 3
    ellipse = 4
    rect = 5
    line = 6

def get_emoji(num: int):
    emj = emoji_data[num]
    # print(emj['short_name'])
    if 'skin_variations' not in emj:
        sheet_x = emj['sheet_x']
        sheet_y = emj['sheet_y']
    else:
        emj = emj['skin_variations'][random.choice(list(emj['skin_variations'].keys()))]
        sheet_x = emj['sheet_x']
        sheet_y = emj['sheet_y']

    sheet_size = 256
    x = (sheet_x * (sheet_size + 2)) + 1;
    y = (sheet_y * (sheet_size + 2)) + 1;

    return emoji_atlas.crop((x, y, x + sheet_size, y + sheet_size)).convert("RGBA")

def get_emote(num: int):
    emt = emote_data[num]
    # print(emt['name'])
    sheet_x = emt['sheet_x']
    sheet_y = emt['sheet_y']

    sheet_size = 128
    x = sheet_x * sheet_size
    y = sheet_y * sheet_size

    return emote_atlas.crop((x, y, x + sheet_size, y + sheet_size)).convert("RGBA")

def fill_object(obj: dict):
    if obj["objtype"] == Object.image:
        atlas = randint(0,1)
        obj["atlas"] = atlas
        match atlas:
            case 0:
                emoji_side = 256
                obj_num = randint(0, len(emoji_data) - 1)
                emjw = randint(emoji_side // 4, emoji_side)
                emjh = randint(emoji_side // 4, emoji_side)
            case 1:
                emoji_side = 128
                obj_num = randint(0, len(emote_data) - 1)
                emjw = randint(emoji_side // 2, emoji_side * 2)
                emjh = randint(emoji_side // 2, emoji_side * 2)

        obj["w"] = emjw
        obj["h"] = emjh
        obj["num"] = obj_num
    elif obj["objtype"] == Object.text:
        obj["num"] = randint(0, len(words) - 1)
        obj["size"] = randint(40, 72)
    elif obj["objtype"] == Object.char:
        obj["num"] = randint(33, 126)
        obj["size"] = randint(40, 72)
    elif (obj["objtype"] == Object.ellipse or
          obj["objtype"] == Object.rect):
        obj["w"] = randint(200, 400)
        obj["h"] = randint(200, 400)
    elif obj["objtype"] == Object.line:
        obj["x2"] = randint(0, img_side)
        obj["y2"] = randint(0, img_side)

def randpos(obj: dict):
    xpos = randint(img_side // 8, 6 * img_side // 8)
    ypos = randint(img_side // 8, 6 * img_side // 8)
    obj["xpos"] = xpos
    obj["ypos"] = ypos

def new_object() -> dict:
    objtype = Object(randint(1,len(Object)))
    obj = {"objtype": objtype}
    randpos(obj)
    fill_object(obj)
    return obj

def transform_object(obj: dict):
    obj["objtype"] = Object((obj["objtype"].value + 1) % len(Object) + 1)
    fill_object(obj)

def draw_object(obj: dict, img: Image, draw: ImageDraw.Draw):
    if obj["objtype"] == Object.image:
        match obj["atlas"]:
            case 0:
                emoji_side = 256
                obj_img = get_emoji(obj["num"])
            case 1:
                emoji_side = 128
                obj_img = get_emote(obj["num"])
        obj_img = obj_img.resize((obj["w"], obj["h"]))
        img.paste(obj_img, (obj["xpos"], obj["ypos"]), obj_img)
    elif obj["objtype"] == Object.text:
        fnt = ImageFont.truetype("FreeMono.ttf", obj["size"])
        draw.text((obj["xpos"], obj["ypos"]), words[obj["num"]], font=fnt, fill=(0, 0, 0))
    elif obj["objtype"] == Object.char:
        fnt = ImageFont.truetype("FreeMono.ttf", obj["size"])
        draw.text((obj["xpos"], obj["ypos"]), chr(obj["num"]), font=fnt, fill=(0, 0, 0))
    elif obj["objtype"] == Object.ellipse:
        draw.ellipse([(obj["xpos"], obj["ypos"]), (obj["xpos"] + obj["w"], obj["ypos"] + obj["h"])], fill=(randint(0, 200), randint(0, 200), randint(0, 200)), outline=None)
    elif obj["objtype"] == Object.line:
        draw.line([(obj["xpos"], obj["ypos"]), (obj["x2"], obj["y2"])], fill=(randint(0, 200), randint(0, 200), randint(0, 200)), width = randint(5, 10))
    elif obj["objtype"] == Object.rect:
        draw.rectangle([(obj["xpos"], obj["ypos"]), (obj["xpos"] + obj["w"], obj["ypos"] + obj["h"])], fill=(randint(0, 200), randint(0, 200), randint(0, 200)), outline=None)
    else:
        assert 0

def executor(cmd: str) -> Image:

    # print(cmd[0:8])
    seed = int(hashlib.sha1(cmd[0:8].encode("utf-8")).hexdigest(), 16) % (10 ** 8)
    # print(f"seed: {seed}")
    random.seed(seed)

    r = randint(50, 200)
    g = randint(50, 200)
    b = randint(50, 200)

    img = Image.new('RGB', (img_side, img_side), color=(r, g, b))
    draw = ImageDraw.Draw(img)

    objects = []
    for _ in range(0, randint(1, 5)):
        objects += [new_object()]
    # print(objects)
    cur_object = 0
    b = bytes(cmd, 'utf-8')
    for byte in b:
        add = False
        char = chr(byte)
        match char:
            case 'A':
                instr = 'ADD'
                add = True
            case 'B':
                instr = 'BRING'
                add = True
            case 'C':
                instr = 'COLOR'
            case 'D':
                instr = 'DOUBLE'
                doubled = objects[cur_object].copy()
                randpos(doubled)
                objects += [doubled]
            case 'E':
                instr = 'ESTABLISH'
                add = True
            case 'F':
                instr = 'FORWARD'
            case 'G':
                instr = 'GRAB'
            case 'H':
                instr = 'HIDE'
            case 'I':
                instr = 'INSERT'
                add = True
            case 'J':
                instr = 'JUMP'
            case 'K':
                instr = 'KILL'
            case 'L':
                instr = 'LOOP'
            case 'M':
                instr = 'MOVE'
            case 'N':
                instr = 'NEXT'
                cur_object = (cur_object + 1) % len(objects)
            case 'O':
                instr = 'OUTPUT'
                add = True
            case 'P':
                instr = 'PUT'
            case 'Q':
                instr = 'QUADRUPLE'
            case 'R':
                instr = 'ROTATE'
            case 'S':
                instr = 'SCALE'
            case 'T':
                instr = 'TRANSFORM'
                transform_object(objects[cur_object])
            case 'U':
                instr = 'UNVEIL'
                add = True
            case 'V':
                instr = 'VIEW'
            case 'W':
                instr = 'WIDE'
            case 'X':
                instr = 'XEROX'
            case 'Y':
                instr = 'YIELD'
                add = True
            case 'Z':
                instr = 'ZOOM'
            case '_':
                instr = '_MORE'
                add = True
            case _:
                instr = 'UNKNOWN'
        # print(f"{byte}:\t'{char}'\t{instr}")
        # print(objects)
        if add and len(objects) < obj_limit:
            objects += [new_object()]
    for obj in objects:
        draw_object(obj, img, draw)
    return img

if __name__ == "__main__":
    path_str = ''
    if len(sys.argv) > 1:
        path_str = sys.argv[1]
    if path_str == '':
        path_str=''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

    print("Generating image for '%s'" % path_str)
    img = executor(path_str)
    img_path = "output.png"
    img.save(img_path)
    print("Saved image to '%s'" % img_path)
