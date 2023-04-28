#!/usr/bin/env python3
from pypresence import Presence
from pathlib import Path
import requests, datetime, json
import socket, base64

config_file = Path("~/.config/richspot.json").expanduser()
pods_file = Path("~/.config/richspot_pods.json").expanduser()
socket_file = Path("~/.cache/ncspot/ncspot.sock").expanduser().as_posix()

if not config_file.exists():
    config_file.touch()
    pods_file.touch()
    tk = input("[+]: Enter Client ID: ")
    uk = input("[+]: Enter Authorization Token: ")
    with open(config_file, 'w') as config:
        data = {'client_id': tk, 'user_token': uk}
        json.dump(data, config)

def read_file(file):
    try:
        with open(file, 'r') as filer:
            return json.load(filer)
    except Exception:
        return {}

def write_file(file, data):
    with open(file, 'w') as filer:
        json.dump(data, filer)

config = read_file(config_file)
client_id = str(config['client_id'])
user_token = config['user_token']
RPC = Presence(client_id)
RPC.connect()
list_covers = []

def image_asset(link, title):
    """ Upload / Delete Image to discord assets """
    assets_url = f'https://discord.com/api/v9/oauth2/applications/{client_id}/assets'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': user_token,
    }
    assets = requests.get(assets_url, headers=headers)
    assets_list = json.loads(assets.content.decode())
    image_b64 = requests.get(link)
    image_b64 = base64.b64encode(image_b64.content).decode()
    remove_chars = ",.: '"
    img_title = title.translate(str.maketrans('', '', remove_chars)).lower()
    image_data = {
        'name': f"{img_title}",
        'image': f"data:image/png;base64,{image_b64}",
        'type': "1"
    }
    # delete eall assets
    # for asset in assets_list:
    #     requests.delete(assets_url+f"/{asset['id']}", headers=headers)
    if len(assets_list) <= 300:
        if not any(asset['name'] == img_title for asset in assets_list) and not any(img_title == img_c for img_c in list_covers):
            list_covers.append(img_title)
            upload_image = requests.post(assets_url, headers=headers, json=image_data)
            # print(upload_image.content)
    else:
        last_assets = assets_list[-10:]
        for assets in last_assets:
            requests.delete(assets_url+f"/{assets['id']}", headers=headers)
            image_asset(assets_url, title)

def check_pod(url):
    """Check if podcast cover image is repeatable."""
    pod_data = read_file(pods_file)
    ep_data = {url.split("/")[-1]: url}
    if not pod_data:
        pod_data = {"purls": []}
        pod_data['purls'].append(url)
        pod_data.update(ep_data)
        write_file(pods_file, pod_data)
        image_asset(url, url.split("/4")[-1])
    else:
        if url not in pod_data["purls"]:
            pod_data["purls"].append(url)
            pod_data.update(ep_data)
            write_file(pods_file, pod_data)
            image_asset(url, url.split("/4")[-1])
    return url.split('/')[-1]

def getmusic():
    """ Connect to ncspot and get metadata and update rich presence """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_file)
    while True:
        data = sock.recv(4096)
        song_info = json.loads(data.decode())
        try:
            mode = list(song_info["mode"].keys())[0]
        except Exception:
            mode = song_info.get("mode", "Stopped")
        type_track = song_info['playable']['type']
        cover_url = song_info["playable"]["cover_url"]
        url = song_info["playable"]["uri"]
        duration = song_info["playable"]["duration"]
        if type_track != "Episode":
            title = song_info["playable"]["title"]
            artists = song_info["playable"]["artists"]
            album = song_info["playable"]["album"]
            details = title
            state = f"By {artists[0]}\nAlbum: {album}"
            cover_img = title.replace(" ", "").lower()
            image_asset(cover_url, title)
        else:
            title = song_info['playable']['name']
            details = "Podcast"
            state = title
            cover_img = check_pod(cover_url)

        if mode == "Playing":
            time_start = song_info["mode"]["Playing"]['secs_since_epoch']
            end_time = datetime.datetime.fromtimestamp(time_start)
            end_time += datetime.timedelta(milliseconds=duration)
            end_time = int(end_time.timestamp())
            RPC.update(details=details, state=state, start=time_start, end=end_time, join=url, large_image=cover_img, small_image=cover_img, large_text="Deez Nuts")

        else:
            RPC.update(details=details+" (Paused/Stopped)", state=state, join=url, large_image=cover_img, small_image=cover_img, large_text="Deez Nuts")

def run():
    """ Run Continuously and don't stop """
    while True:
        try:
            getmusic()
        except Exception as e:
            print(f"Error: {e}")
            continue
