import gen

import hashlib
import json
import random
import re
import string

from flask import Flask, Response, send_file, redirect, request
from io import BytesIO
from urllib.parse import urlparse
import urllib.request
import urllib.parse

app = Flask(__name__)

def serve_pil_image(pil_img):
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

f = open("emote_ids.json")
emote_ids = json.load(f)
f.close()

def serve_discord_emote(id, animated=False):
    format = "gif" if animated else "webp"
    animated = "true" if animated else "false"
    link = f'http://cdn.discordapp.com/emojis/{id}.{format}?size=96&animated={animated}'
    # print(link)
    qs = urllib.parse.urlencode(request.args.to_dict(), doseq=True)
    url = link
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "image/gif",
        "Accept-Language": "en-US,en;q=0.9"
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            content_type = "image/gif"
            content_length = resp.headers.get("Content-Length", str(len(data)))
            return Response(data, status=resp.getcode(), headers={
                "Content-Type": content_type,
                "Content-Length": content_length
            })
    except urllib.error.HTTPError as e:
        pass
    except urllib.error.URLError:
        pass

    return None

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_img(path):
    o = urlparse(request.base_url)
    host = o.hostname
    # print(host)
    if host[0] == '🟠':
        return send_file('squirtle.gif', mimetype='image/png')

    path_str = path
    request_str = request.query_string.decode('utf-8')

    if request_str != '':
        path_str += '?'
        path_str += request_str
    if path_str == '':
        new_path="http://" + host + '/' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        return redirect(new_path)

    if host[0] == '🇪':
        g = random.Random()
        seed = int(hashlib.sha1(path_str[0:8].encode("utf-8")).hexdigest(), 16) % (10 ** 8)
        g.seed(seed)
        num = g.randint(0, len(emote_ids) - 1)
        res = serve_discord_emote(emote_ids[num]["id"], emote_ids[num]["animated"])
        if res:
            return res

    match = re.search(r'^emojis/(\d+)(\.(png|gif|webp))?', path_str)
    if match:
        res = serve_discord_emote(match.group(1), match.group(2) == '.gif')
        if res:
            return res

    img = gen.executor(path_str)
    return serve_pil_image(img)

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r
