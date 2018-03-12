import websocket
import requests
import json
import time
import threading
from dateutil import parser
import os

threads = {}

class MyThread(threading.Thread):
    def __init__(self, username, channel, ws, *args, **kwargs):
        super(MyThread, self).__init__(*args, **kwargs)
        self.stop = threading.Event()
        self.username = username
        self.channel = channel
        self.ws = ws

    def run(self):
        base_url = 'https://api.github.com/users/' + self.username + '/events'
        res = requests.get(base_url)
        if res.status_code == 404:
            self.ws.send(json.dumps({
                'channel': self.channel,
                'type': 'message',
                'text': 'User not found'
            }))
            return
        self.ws.send(json.dumps({
            'channel': self.channel,
            'type': 'message',
            'text': 'Registered user ' + self.username
        }))
        ETag = res.headers['ETag']
        limit = res.headers['X-Poll-Interval']
        
        log(res.status_code, limit, res.headers['X-RateLimit-Remaining'], ETag)
        latest_time = parser.parse(res.json()[0]['created_at'])

        while not self.stop.is_set():
            try:
                # time.sleep(int(res.headers['X-Poll-Interval']))
                time.sleep(10)
                res = requests.get(base_url, headers={'If-None-Match': ETag})

                ETag = res.headers['ETag']
                log(res.status_code, limit, res.headers['X-RateLimit-Remaining'], ETag)

                if res.status_code != 304:
                    print(res.headers)
                    limit = res.headers['X-Poll-Interval']
                    datas = list(filter(lambda x: parser.parse(x['created_at']) > latest_time, res.json()))
                    print(datas)
                    latest_time = parser.parse(res.json()[0]['created_at'])
                    self.ws.send(json.dumps({
                        'channel': self.channel,
                        'type': 'message',
                        'text': 'Update from user ' + self.username + ': \n' + json.dumps(datas)
                    }))
            except Exception as e:
                print(e)
        print('Thread stopped')

def log(code, interval, limit, etag):
    print('Status Code:', code)
    print('Polling Interval:', interval, ', Ratelimit Remaining:', limit)
    print('ETag:', etag)


def message(ws, message):
    print(message)
    message = json.loads(message)
    if 'type' not in message or message['type'] != 'message':
        return
    if message['text'].startswith('!github_register'):
        username = message['text'].split()[1]
        if username in threads.keys():
            ws.send(json.dumps({
                'channel': message['channel'],
                'type': 'message',
                'text': 'User already registered'
            }))
        else:
            threads[username] = MyThread(username=username, channel=message['channel'], ws=ws)
            threads[username].username = username
            threads[username].start()
            
    elif message['text'].startswith('!github_unregister'):
        username = message['text'].split()[1]
        if username not in threads.keys():
            ws.send(json.dumps({
                'channel': message['channel'],
                'type': 'message',
                'text': 'No such user'
            }))
        else:
            threads[username].stop.set()
            ws.send(json.dumps({
                'channel': message['channel'],
                'type': 'message',
                'text': 'User removed'
            }))
