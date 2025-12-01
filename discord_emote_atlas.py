#!/bin/env python3

import os
import math
import PIL
import json

from PIL import Image, ImageDraw, ImageFont

emote_dir = '../tsoding_discord_emotes'
emotes=os.listdir(emote_dir)
emotes = emotes[:-15]

emote_side = 128
emotes_by_row = 16
columns = emotes_by_row
rows = math.ceil(len(emotes) / 16)
atlas = Image.new('RGBA', (emote_side * columns, emote_side * rows), color=(0, 0, 0, 0))
metadata=[]

for i, emote in enumerate(emotes):
    img = Image.open(f"{emote_dir}/{emote}")
    img = img.resize((emote_side,emote_side))
    width, height = img.size
    print(f"{emote}: {width}x{height}: {i}: x:{i%columns}, y:{i//columns}")
    sheet_x = i%columns
    sheet_y = i//columns
    atlas.paste(img, (sheet_x*emote_side, sheet_y*emote_side))
    metadata += [{"name": emote.split('.')[0], "sheet_x": sheet_x, "sheet_y": sheet_y}]
    img.close()
atlas.save('emotes.png')

with open('emotes.json', 'w', encoding='utf-8') as f:
    json.dump(metadata, f, ensure_ascii=False, indent=4)
