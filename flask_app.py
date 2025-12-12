import gen

import random
import string

from flask import Flask, send_file, redirect, request
from io import BytesIO

app = Flask(__name__)

def serve_pil_image(pil_img):
    img_io = BytesIO()
    pil_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_img(path):
    path_str = path
    request_str = request.query_string.decode('utf-8')
    if request_str != '':
        path_str += '?'
        path_str += request_str
    if path_str == '':
        new_path='/' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        return redirect(new_path)

    img = gen.executor(path_str)
    return serve_pil_image(img)

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r
