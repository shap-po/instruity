import youtube_dl
from pprint import pformat
try:
    from __init__ import playlists as final
except ImportError:
    raise
    final = {}

try:
    from __init__ import info
except ImportError:
    # raise
    info = {}

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}
ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)


def create_playlist(url):
    processed_info = ytdl.extract_info(url, download=False)
    playlist = []
    if not 'entries' in processed_info:
        return [processed_info['webpage_url']]
    for entry in processed_info['entries']:
        if entry:
            playlist.append(entry['webpage_url'])
    return playlist


def format(text):
    return pformat(text).replace('{', '{\n')


playlists = {'epic': [
    'https://www.youtube.com/playlist?list=PLrjo8kFr6wuy9x38Imyb3bOvP7vfqpsvb']}
#playlists = {'test': ['https://www.youtube.com/playlist?list=PLLdhzT83SscRI4saA8itRwElf_aKBAHwW']}


for id, lists in playlists.items():
    if not id in final:
        final[id] = []
    if not id in info:
        info[id] = []
    for plist in lists:
        final[id] += create_playlist(plist)
        info[id] += lists
    final[id] = list(set(final[id]))
    info[id] = list(set(info[id]))


final = format(final)
info = format(info)
with open('__init__.py', 'w') as f:
    f.write(f'playlists = {final}\n\ninfo = {info}')

print('Finished')
