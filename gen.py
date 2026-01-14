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
emoji_atlas = Image.open("sheet_twitter_256_indexed_256.png").convert("RGBA")
emote_atlas = Image.open("emotes.png")

@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

class Atlas:
    def __init__(self, atlas, data, pic_side, padding=1):
        self.atlas = atlas
        self.data = data
        self.pic_side = pic_side
        self.padding = padding

    def get_pic(self, num: int):
        pic = self.data[num]
        sheet_x = pic['sheet_x']
        sheet_y = pic['sheet_y']
        # print(pic['name'])

        x = (sheet_x * (self.pic_side + 2 * self.padding)) + self.padding
        y = (sheet_y * (self.pic_side + 2 * self.padding)) + self.padding
        pic = self.atlas.crop((x, y, x + self.pic_side, y + self.pic_side))
        pic = pic.crop(pic.getbbox())
        return pic

    def rnd_pic(self):
        num = randint(0, len(self.data) - 1)
        return self.get_pic(num)

atlases = [Atlas(emoji_atlas, emoji_data, 256, 1), Atlas(emote_atlas, emote_data, 128, 0)]

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
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y
        self.atlas = atlases[randint(0,1)]
        self.img = self.atlas.rnd_pic()
        ratio = self.img.width / self.img.height
        new_h = int((self.img.height / self.atlas.pic_side) * 200)
        new_w = int(new_h * ratio)
        self.img = self.img.resize((new_w, new_h))
        self.w = self.img.width
        self.h = self.img.height

    def shift(self, x: int, y: int):
        self.x += x
        self.y += y

    def draw(self, img: Image, d: ImageDraw):
        obj_img = self.img.resize((self.w, self.h))
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
    def __init__(self, x=0, y=0, stretch=1.0):
        self.img = Picture()
        self.el = Ellipse()
        self.center = Ellipse(fill=True)
        self.height = Line()
        self.cross_x = Line()
        self.cross_y = Line()
        ratio = self.img.w / self.img.h
        print(stretch)
        self.h = int(self.img.h * stretch)
        self.x = 0
        self.y = 0
        self.img.h = self.h
        self.img.w = int(self.h * ratio)
        self.el.w = self.img.w
        self.el.h = self.img.h // 2
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

def randcolor():
    r = randint(50, 200)
    g = randint(50, 200)
    b = randint(50, 200)
    return (r, g, b)

def executor(cmd: str) -> Image:
    seed = int(hashlib.sha1(cmd[0:8].encode("utf-8")).hexdigest(), 16) % (10 ** 8)
    random.seed(seed)

    nlayers = randint(1, 5)
    groups = []
    first = randint(img_side // 2 + 50, img_side - 50)
    last = randint(50, img_side // 2 - 50)
    layers = [last]
    diff = first - last
    left = diff
    print(last, first)
    for i in range(1, nlayers):
        layer_min=int(diff/100*10)
        layer_max=int(diff/100*(100/(nlayers-1)))
        layer_y=randint(layer_min, layer_max)
        if layer_y > left:
            layer_y = left
        print(i, ":", layer_y)
        layers += [layers[i-1]+layer_y]
        print(layers)
        left -= layer_y
    if nlayers >= 2:
        drain = randint(0, nlayers-2)
        for i in range(drain, nlayers):
            layers[i] += left
    # sys.exit(1)
    print(layers)
    for layer in range(0, nlayers):
        print(layer)
        layer_y = layers[layer]
        stretch=min(1.0-(first-layer_y)/diff+0.3, 1.0)
        print(stretch)
        nactors = randint(1, 4)
        group = []
        for _ in range(0,nactors):
            x=randint(0, img_side)
            group += [Actor(x=x, y=layer_y, stretch=stretch)]
        groups += [group]
    img_rect = Rect(0, 0, img_side, img_side)
    for group in groups:
        for actor in group:
            rect_union(img_rect, actor.rect)

    bgcolor = randcolor()

    img_w = img_rect.w - img_rect.x
    img_h = img_rect.h - img_rect.y

    img = Image.new('RGB', (img_w, img_h), color=bgcolor)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (img_w, -img_rect.y+layers[0])], fill=randcolor(), outline=None)
    if debug:
        for layer in range(0, nlayers):
            layer_y = layers[layer]
            d.line([(-img_rect.x, -img_rect.y+layer_y), (-img_rect.x+img_side, -img_rect.y+layer_y)], fill=(0, 0, 0), width = 1)

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
