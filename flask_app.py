import random
import string
import json
import PIL

from flask import Flask, send_file, redirect
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from random import randint

f = open("emoji_pretty.json")
emoji_data = json.load(f)
f.close()

f = open("emotes.json")
emote_data = json.load(f)
f.close()

PIL.Image.MAX_IMAGE_PIXELS = 255872016
emoji_atlas = Image.open("sheet_twitter_256_indexed_256.png")
emote_atlas = Image.open("emotes.png")

def rnd_emoji():
    emj = emoji_data[randint(0, len(emoji_data))]
    print(emj['short_name'])
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

def rnd_emote():
    emt = emote_data[randint(0, len(emote_data))]
    print(emt['name'])
    sheet_x = emt['sheet_x']
    sheet_y = emt['sheet_y']
    
    sheet_size = 128
    x = sheet_x * sheet_size
    y = sheet_y * sheet_size
    
    return emote_atlas.crop((x, y, x + sheet_size, y + sheet_size)).convert("RGBA")

app = Flask(__name__)

def serve_pil_image(pil_img):
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_img(path):
    if path == '':
        new_path='/' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        return redirect(new_path)

    img_side=800
    r = randint(0, 255)
    g = randint(0, 255)
    b = randint(0, 255)
    img = Image.new('RGB', (img_side, img_side), color=(r, g, b))

    draw = ImageDraw.Draw(img)
    fnt = ImageFont.truetype("FreeMono.ttf", 40)

    if randint(0,1) == 1:
        emoji_img = rnd_emoji()
        emoji_side=256
    else:
        emoji_img = rnd_emote()
        emoji_side=128
    txt = "Hello, World!"
    
    center = int(img_side / 2)
    emj_center = int(emoji_side / 2)
    text_box = draw.textbbox((center, center), txt, font=fnt)
    text_center = int((text_box[2] - text_box[0]) / 2)
    img.paste(emoji_img, (center - emj_center, center - emj_center), emoji_img)
    draw.text((center - text_center, center + emj_center), txt, font=fnt, fill=(0, 0, 0))

    return serve_pil_image(img)

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r
