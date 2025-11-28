import random
import string
import json

from flask import Flask, send_file, redirect, url_for
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from random import randint
from random_unicode_emoji import random_emoji

f = open("emoji_pretty.json")
emjdata = json.load(f)
f.close()
atlas = Image.open("sheet_twitter_64_indexed_256.png")
skins = list(range(0x1F3FB, 0x1F3FF + 1))

def rndimg():
    emj = random_emoji()[0]
    print(emj)
    filtered=[]
    skin_used=[]
    for char in emj:
        if ord(char) not in skins:
            filtered += [char]
        else:
            skin_used += [char]
    key = "-".join([f"{ord(char):04x}".upper() for char in filtered])
    found = [emj for emj in emjdata if emj["unified"] == key or emj["non_qualified"] == key]
    print([emj['short_name'] for emj in found])
    if not skin_used:
        sheet_x = found[0]['sheet_x']
        sheet_y = found[0]['sheet_y']
    else:
        skin_var = "-".join([f"{ord(char):04x}".upper() for char in skin_used])
        skin_var = found[0]['skin_variations'][skin_var]
        sheet_x = skin_var['sheet_x']
        sheet_y = skin_var['sheet_y']
    
    sheet_size = 64
    x = (sheet_x * (sheet_size + 2)) + 1;
    y = (sheet_y * (sheet_size + 2)) + 1;
    
    return atlas.crop((x, y, x + sheet_size, y + sheet_size)).convert("RGBA")

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
    r = randint(0, 255)
    g = randint(0, 255)
    b = randint(0, 255)
    img = Image.new('RGB', (800, 800), color=(r, g, b))

    draw = ImageDraw.Draw(img)
    fnt = ImageFont.truetype("FreeMono.ttf", 40)
    draw.text((10, 60), "World!", font=fnt, fill=(255, 255, 255))

    emoji_img = rndimg()
    img.paste(emoji_img, (0, 0), emoji_img)

    img.show()
    return serve_pil_image(img)

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r
