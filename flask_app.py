import random
import string
import json

from flask import Flask, send_file, redirect
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from random import randint

f = open("emoji_pretty.json")
emjdata = json.load(f)
f.close()
atlas = Image.open("sheet_twitter_64_indexed_256.png")

def rndimg():
    emj = emjdata[randint(0, len(emjdata))]
    print(emj['short_name'])
    if 'skin_variations' not in emj:
        sheet_x = emj['sheet_x']
        sheet_y = emj['sheet_y']
    else:
        emj = emj['skin_variations'][random.choice(list(emj['skin_variations'].keys()))]
        sheet_x = emj['sheet_x']
        sheet_y = emj['sheet_y']
    
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
