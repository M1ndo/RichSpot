#!/usr/bin/env python3
from pypresence import Presence
from pathlib import Path
import requests, datetime, json
import socket, base64, os

config_file = Path("~/.config/richspot.json").expanduser()
pods_file = Path("~/.config/richspot_pods.json").expanduser()
socket_file = Path(f"/run/user/{os.getuid()}/ncspot/ncspot.sock").expanduser().as_posix()

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

def image_asset(link, title):
    """ Upload / Delete Image to discord assets """
    assets_url = f'https://discord.com/api/v9/oauth2/applications/{client_id}/assets'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': user_token,
    }
    assets = requests.get(assets_url, headers=headers)
    assets_list = json.loads(assets.content.decode())
    cover_names = [asset['name'] for asset in assets_list]
    image_b64 = requests.get(link)
    image_b64 = base64.b64encode(image_b64.content).decode()
    remove_chars = ",.: '"
    img_title = title.translate(str.maketrans('', '', remove_chars)).lower()
    image_data = {
        'name': f"{img_title}",
        'image': f"data:image/png;base64,{image_b64}",
        'type': "1"
    }
    to_delete = remove_dups(assets_list)
    if to_delete:
        for item in to_delete:
            requests.delete(assets_url+f"/{item}", headers=headers)
    # delete eall assets
    # for asset in assets_list:
    #     requests.delete(assets_url+f"/{asset['id']}", headers=headers)
    if len(assets_list) != 300:
        if img_title not in cover_names:
            requests.post(assets_url, headers=headers, json=image_data)
    else:
        last_assets = assets_list[-10:]
        for assets in last_assets:
            requests.delete(assets_url+f"/{assets['id']}", headers=headers)
        image_asset(link, title)

def remove_dups(assets: list) -> list:
    """ Find and removes duplicates a FIX for older versions before >1.2 """
    name_to_assets = {}
    to_delete = []
    for asset in assets:
        name = asset['name']
        if name in name_to_assets:
            name_to_assets[name].append(asset)
        else:
            name_to_assets[name] = [asset]
    for assets in name_to_assets.values():
        if len(assets) > 1:
            n1 = assets[0]['id']
            for i, asset in enumerate(assets):
                if i != 0 and asset['id'] != n1:
                    to_delete.append(asset['id'])
    return to_delete

def check_url(url, pod_data, title=''):
    """ Check if podcast/song cover image is already uploaded."""
    if not title: title = url.split("/4")[-1]
    if not pod_data:
            pod_data = {"purls": [url]}
            image_asset(url, title)
    else:
        if url not in pod_data["purls"]:
            pod_data["purls"].append(url)
            image_asset(url, title)
    write_file(pods_file, pod_data)
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
        pod_data = read_file(pods_file)
        if type_track != "Episode":
            title = song_info["playable"]["title"]
            artists = song_info["playable"]["artists"]
            album = song_info["playable"]["album"]
            details = title
            state = f"By {artists[0]}\nAlbum: {album}"
            cover_img = title.replace(" ", "").lower()
            check_url(cover_url, pod_data, title=title)
        else:
            title = song_info['playable']['name']
            details = "Podcast"
            state = title
            cover_img = check_url(cover_url, pod_data)

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
