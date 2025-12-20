#!/bin/env python3

import random
import string
import json
import PIL
import hashlib
import sys

from PIL import Image, ImageDraw, ImageFont
from random import randint, uniform
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass

words = ["HELLO", "Hello", "Young", "Stranger", "ABSOLUTE", "CODING", "TSODING", "DEEZ", "NUTS", "URMOM"]
img_side=800
obj_limit = 15
debug=True
debug=False

f = open("emoji_pretty.json")
emoji_data = json.load(f)
f.close()

f = open("emotes.json")
emote_data = json.load(f)
f.close()

PIL.Image.MAX_IMAGE_PIXELS = 255872016
emoji_atlas = Image.open("sheet_twitter_256_indexed_256.png")
emote_atlas = Image.open("emotes.png")

@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

class Object(ABC):
    @abstractmethod
    def shift(self, x: int, y: int):
        pass

    @abstractmethod
    def draw(self, img: Image, d: ImageDraw):
        pass

    @property
    @abstractmethod
    def rect(self) -> Rect:
        pass

def rect_union(big: Rect, rect: Rect):
    if rect.x < big.x:
        big.x = rect.x 
    if rect.y < big.y:
        big.y = rect.y 
    if rect.w > big.w:
        big.w = rect.w 
    if rect.h > big.h:
        big.h = rect.h 

class Picture(Object):
    def __init__(self, x=0, y=0, w=10, h=10):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.atlas = randint(0,1)
        match self.atlas:
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

        self.w = emjw
        self.h = emjh
        self.num = obj_num

    def shift(self, x: int, y: int):
        self.x += x
        self.y += y

    def draw(self, img: Image, d: ImageDraw):
        match self.atlas:
            case 0:
                emoji_side = 256
                obj_img = get_emoji(self.num)
            case 1:
                emoji_side = 128
                obj_img = get_emote(self.num)
        obj_img = obj_img.resize((self.w, self.h))
        img.paste(obj_img, (self.x, self.y), obj_img)

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.x + self.w, self.y + self.h)

class Text(Object):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

class Char(Object):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y


class Ellipse(Object):
    def __init__(self, x=0, y=0, fill=False, w=10, h=10, color=(0, 0, 0)):
        self.x = x
        self.y = y
        self.fill = fill
        self.color = color
        self.w = w
        self.h = h

    def shift(self, x: int, y: int):
        self.x += x
        self.y += y

    def draw(self, img: Image, d: ImageDraw):
        params = {}
        if self.fill:
            params.update({"fill": self.color, "outline": None})
        else:
            params.update({"outline": self.color, "fill": None})
        d.ellipse([(self.x, self.y), (self.x + self.w, self.y + self.h)], **params)

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.x + self.w, self.y + self.h)

class Rectangle(Object):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

class Line(Object):
    def __init__(self, x=0, y=0, x2=0, y2=0, width=1, color=(0,0,0)):
        self.x = x
        self.y = y
        self.x2 = x2
        self.y2 = y2
        self.width = width
        self.color = color

    def shift(self, x: int, y: int):
        self.x += x
        self.y += y
        self.x2 += x
        self.y2 += y

    def draw(self, img: Image, d: ImageDraw):
        d.line([(self.x, self.y), (self.x2, self.y2)], fill=self.color, width = self.width)

    @property
    def rect(self) -> Rect:
        return Rect(min(self.x, self.x2), 
                    min(self.y, self.y2),
                    max(self.x2, self.x),
                    max(self.y2, self.y))

class Actor(Object):
    def __init__(self, x=0, y=0, height=10):
        self.el = Ellipse()
        self.el.w = randint(100, 200)
        self.el.h = self.el.w // 2
        self.center = Ellipse(fill=True)
        self.h = height
        self.height = Line()
        self.cross_x = Line()
        self.cross_y = Line()
        self.x = 0
        self.y = 0
        self.img = Picture()
        self.img.h = self.h
        self.img.w = self.el.w
        self.shift(x, y)
    
    def shift(self, x: int, y: int):
        self.x += x
        self.y += y
        self.el.x = self.x - self.el.w // 2
        self.el.y = self.y - self.el.h // 2
        self.center.x = self.x - self.center.w // 2
        self.center.y = self.y - self.center.h // 2
        self.height.x = self.x
        self.height.y = self.y
        self.height.x2 = self.height.x
        self.height.y2 = self.height.y - self.h
        
        self.cross_x.x = self.x
        self.cross_x.y = self.el.y
        self.cross_x.x2 = self.x
        self.cross_x.y2 = self.el.y + self.el.h
    
        self.cross_y.x = self.el.x
        self.cross_y.y = self.y
        self.cross_y.x2 = self.el.x + self.el.w
        self.cross_y.y2 = self.y

        self.img.x = self.el.x
        self.img.y = self.height.y2

    @property
    def rect(self) -> Rect:
        rect = Rect(0,0,0,0)
        rect_union(rect, self.el.rect)
        rect_union(rect, self.center.rect)
        rect_union(rect, self.height.rect)
        return rect

    def draw(self, img: Image, d: ImageDraw):
        if debug:
            self.el.draw(img, d)
            self.cross_x.draw(img, d)
            self.cross_y.draw(img, d)
        self.img.draw(img, d)
        if debug:
            self.height.draw(img, d)
            self.center.draw(img, d)

def get_emoji(num: int):
    emj = emoji_data[num]
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
    sheet_x = emt['sheet_x']
    sheet_y = emt['sheet_y']

    sheet_size = 128
    x = sheet_x * sheet_size
    y = sheet_y * sheet_size

    return emote_atlas.crop((x, y, x + sheet_size, y + sheet_size)).convert("RGBA")

def fill_object(obj: dict, **kwargs):
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
        obj["fill"] = kwargs.get("fill", True)
    elif obj["objtype"] == Object.line:
        obj["x2"] = randint(0, img_side)
        obj["y2"] = randint(0, img_side)

def randpos(obj: dict):
    xpos = randint(img_side // 8, 6 * img_side // 8)
    ypos = randint(img_side // 8, 6 * img_side // 8)
    obj["xpos"] = xpos
    obj["ypos"] = ypos

def new_object(objtype: Object, **kwargs) -> dict:
    obj = {"objtype": objtype, "xpos": 0, "ypos": 0}
    fill_object(obj, **kwargs)
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
        params = {}
        if obj["fill"]:
            params.update({"fill": (randint(0, 200), randint(0, 200), randint(0, 200)), "outline": None})
        else:
            params.update({"outline": (randint(0, 200), randint(0, 200), randint(0, 200)), "fill": None})
        draw.ellipse([(obj["xpos"], obj["ypos"]), (obj["xpos"] + obj["w"], obj["ypos"] + obj["h"])], **params)
    elif obj["objtype"] == Object.line:
        draw.line([(obj["xpos"], obj["ypos"]), (obj["x2"], obj["y2"])], fill=(randint(0, 200), randint(0, 200), randint(0, 200)), width = randint(5, 10))
    elif obj["objtype"] == Object.rect:
        draw.rectangle([(obj["xpos"], obj["ypos"]), (obj["xpos"] + obj["w"], obj["ypos"] + obj["h"])], fill=(randint(0, 200), randint(0, 200), randint(0, 200)), outline=None)
    else:
        assert 0

def randcolor():
    r = randint(50, 200)
    g = randint(50, 200)
    b = randint(50, 200)
    return (r, g, b)

def executor(cmd: str) -> Image:
    seed = int(hashlib.sha1(cmd[0:8].encode("utf-8")).hexdigest(), 16) % (10 ** 8)
    random.seed(seed)

    horizon_high=50
    horizon = randint(horizon_high, img_side)
    layers = randint(1, 7)
    groups = []
    for layer in range(0, layers):
        layer_y = horizon + ((img_side - horizon) // layers) * layer
        x=randint(0, img_side)
        height=(layer_y-horizon_high)/(img_side)
        height *= 300
        height=int(height)
        groups += [[Actor(x=x, y=layer_y, height=height)]]
    img_rect = Rect(0, 0, img_side, img_side)
    for group in groups:
        for actor in group:
            rect_union(img_rect, actor.rect)

    bgcolor = randcolor()

    img_w = img_rect.w - img_rect.x
    img_h = img_rect.h - img_rect.y

    img = Image.new('RGB', (img_w, img_h), color=bgcolor)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (img_w, horizon)], fill=randcolor(), outline=None)
    if debug:
        for layer in range(0, layers):
            layer_y = horizon + ((img_side - horizon) // layers) * layer
            d.line([(-img_rect.x, -img_rect.y+layer_y), (-img_rect.x+img_side, -img_rect.y+layer_y)], fill=(randint(0, 200), randint(0, 200), randint(0, 200)), width = 1)

    for group in groups:
        for actor in group:
            actor.shift(-img_rect.x, -img_rect.y)
            actor.draw(img, d)
    res = img.crop((-img_rect.x, -img_rect.y, -img_rect.x + img_side, -img_rect.y + img_side))
    return res

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
