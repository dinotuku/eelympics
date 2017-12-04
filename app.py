#!/usr/bin/env python
from importlib import import_module
import json
import os
from flask import Flask, render_template, Response
import http.client, urllib.request, urllib.parse, urllib.error, base64

# Raspberry Pi camera module (requires picamera package)
from camera_pi import Camera
# from camera import Camera

# Load Azure subscription key
from config import CV_KEY, TL_KEY

app = Flask(__name__)
# app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
# app.config['TEMPLATES_AUTO_RELOAD'] = True

cv_headers = {
    # Request headers
    'Content-Type': 'application/octet-stream',
    'Ocp-Apim-Subscription-Key': CV_KEY,
}

tl_headers = {
    # Request headers
    'Ocp-Apim-Subscription-Key': TL_KEY,
}

analyze_params = urllib.parse.urlencode({
    # Request parameters
    'visualFeatures': 'Categories,Description,Faces',
    'details': 'Celebrities,Landmarks',
    'language': 'en',
})

ocr_params = urllib.parse.urlencode({
    # Request parameters
    'detectOrientation': True,
})


@app.route('/')
@app.route('/<cmd>')
def index(cmd=None):
    """Video streaming home page."""
    result = ''
    camera = Camera()
    if cmd == 'image':
        frame = camera.get_frame()
        conn = http.client.HTTPSConnection('eastasia.api.cognitive.microsoft.com')
        conn.request('POST', "/vision/v1.0/analyze?%s" % analyze_params, frame, cv_headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        dec_data = json.loads(data.decode('utf-8'))
        result_list = []
        caption = dec_data['description']['captions'][0]['text']
        result_list.append(caption)
        categories = dec_data['categories'] if 'categories' in dec_data else []
        c_detail = {}
        l_detail = {}
        for cat in categories:
            if cat['name'] == 'people_':
                c_detail = cat['detail'] if 'detail' in cat else {}
            elif cat['name'] == 'outdoor_' or cat['name'] == 'building_':
                l_detail = cat['detail'] if 'detail' in cat else {}
        if c_detail:
            celebrities = []
            for cel in c_detail['celebrities']:
                celebrities.append(cel['name'])
            if celebrities:
                result_list.append(' '.join(celebrities))
        elif l_detail:
            landmarks = []
            for lan in l_detail['landmarks']:
                landmarks.append(lan['name'])
            if landmarks:
                result_list.append(' '.join(landmarks))

        # result = "{}".format(dec_data['description']['captions'][0]['text'])
        result= '\n'.join(result_list)
    elif cmd == 'word':
        frame = camera.get_frame()
        conn = http.client.HTTPSConnection('eastasia.api.cognitive.microsoft.com')
        conn.request('POST', "/vision/v1.0/ocr?%s" % ocr_params, frame, cv_headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        dec_data = json.loads(data.decode('utf-8'))
        words_list = []
        for big_box in dec_data['regions']:
            for small_box in big_box['lines']:
                tmp = []
                for words in small_box['words']:
                    tmp.append(words['text'])
                words_list.append(' '.join(tmp))
        result = '\n'.join(words_list) if len(words_list) != 0 else 'There are no words in the image.'
        tl_params = urllib.parse.urlencode({
            # Request parameters
            'text': result,
            'to': 'zh',
        })
        conn = http.client.HTTPConnection('api.microsofttranslator.com')
        conn.request('GET', "/V2/Http.svc/Translate?%s" % tl_params, headers=tl_headers)
        response = conn.getresponse()
        tl_data = response.read()
        conn.close()
        tl_data = tl_data.replace(b'<string xmlns="http://schemas.microsoft.com/2003/10/Serialization/">', b'')
        tl_data = tl_data.replace(b'</string>', b'')
        dec_tl_data = tl_data.decode('utf-8')
        result = dec_tl_data
    return render_template('index.html', result=result)


def gen(camera):
    """Video streaming generator function."""
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, threaded=True)
