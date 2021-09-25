import asyncio
from asyncio.queues import Queue
import functools
import itertools
import math
import random

import discord
import youtube_dl
from async_timeout import timeout
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext, ComponentContext, cog_ext
from discord_slash.utils.manage_commands import create_option
from discord_slash.utils.manage_components import create_actionrow, create_button
from discord_slash.model import ButtonStyle, CogBaseCommandObject

from playlists import playlists
DEFAULT_VOLUME = 0.35

bot = commands.Bot('-')
slash = SlashCommand(bot)

youtube_dl.utils.bug_reports_message = lambda: ''


def setup_slash():
    guild_ids = [guild.id for guild in bot.guilds]
    for command in list(slash.commands.keys()):
        if command == 'context':
            continue
        slash.commands[command].allowed_guild_ids = guild_ids
    for command in list(slash.subcommands.keys()):
        for subcommand in list(slash.subcommands[command].keys()):
            slash.subcommands[command][subcommand].allowed_guild_ids = guild_ids


def setup_aliases(aliases: dict):
    for command in list(slash.commands.keys()):
        if command == 'context':
            continue
        if command in aliases and command in slash.commands:
            for alias in aliases[command]:
                slash.commands[alias] = slash.commands[command]
                slash.commands[alias].name = alias


def create_actions(actions: dict, elements_in_row: int = 3) -> list:
    if elements_in_row > 5:
        elements_in_row = 5
    action_list = []
    i = 0
    while i < len(actions):
        row = []
        for column in range(elements_in_row):
            if i < len(actions):
                id = list(actions.keys())[i]
                action = list(actions.values())[i]
                row.append(create_button(style=action.style,
                           label=action.label, emoji=action.emoji, custom_id=id))
            i += 1
        action_list.append(create_actionrow(*row))
    return action_list


class SongException(Exception):
    pass


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]

    async def add(self, item):
        if item:
            if isinstance(item, list):
                for i in item:
                    await self.put(i)
            else:
                await self.put(item)

    async def copy(self):
        queue = SongQueue()
        await queue.add(list(self._queue))
        return queue


class Song(discord.PCMVolumeTransformer):
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
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }
    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: SlashContext, source: discord.FFmpegPCMAudio, data: dict, volume: float = DEFAULT_VOLUME):
        super().__init__(source, volume)

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.url = data.get('webpage_url')
        self.stream_url = data.get('url')

        if ctx:
            self.requester = ctx.author
        else:
            self.requester = bot.user
        self.skip_votes = set()

    def __str__(self):
        return f'**{self.title}** от **{self.uploader}**'

    @classmethod
    async def create_source(cls, ctx: SlashContext, search: str, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(
            cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise SongException(
                f'Не удалось найти ничего по запросу: `{search}`')

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise SongException(
                    f'Не удалось найти ничего по запросу: `{search}`')

        if not 'webpage_url' in process_info:
            raise SongException(
                f'Не удалось найти ничего по запросу: `{search}`')

        webpage_url = process_info['webpage_url']
        partial = functools.partial(
            cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise SongException(f'Не удалось получить аудио: `{webpage_url}`')

        if 'entries' not in processed_info:
            info = processed_info
        else:
            playlist = []
            for entry in processed_info['entries']:
                if entry:
                    playlist.append(entry)

            if len(playlist) == 0:
                raise SongException(
                    f'Не удалось получить информацию: `{webpage_url}`')

            return [Song(ctx, discord.FFmpegPCMAudio(info['url'], **Song.FFMPEG_OPTIONS), data=info) for info in playlist]

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    def restart(self):
        super().__init__(discord.FFmpegPCMAudio(
            self.stream_url, **self.FFMPEG_OPTIONS), self.volume)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} дней'.format(days))
        if hours > 0:
            duration.append('{} часов'.format(hours))
        if minutes > 0:
            duration.append('{} минут'.format(minutes))
        if seconds > 0:
            duration.append('{} секунд'.format(seconds))

        return ' '.join(duration)

    def create_embed(self):
        embed = (discord.Embed(title='Сейчас играет',
                               description=f'```\n{self.title}\n```',
                               color=discord.Color.blurple())
                 .add_field(name='Продолжительность', value=self.duration)
                 .add_field(name='Заказано', value=self.requester.mention)
                 .add_field(name='Автор', value=f'[{self.uploader}]({self.uploader_url})')
                 .add_field(name='Ссылка', value=f'[Click]({self.url})')
                 .set_thumbnail(url=self.thumbnail))
        return embed


class VoiceClient:
    def __init__(self, bot: commands.Bot, volume: float = DEFAULT_VOLUME):
        self.bot = bot

        self.voice = None
        self.queue = SongQueue()
        self.current = None
        self.play_next = asyncio.Event()

        self.loop = False
        self.volume = volume
        self.removed = False

        self.queue_before_dnd = None
        self.dnd_playlist = None

        self.audio_player = bot.loop.create_task(self.player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def is_playing(self) -> bool:
        return self.voice and self.current

    async def player_task(self):
        while True:
            self.play_next.clear()

            if not self.loop:
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.queue.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return
            else:
                self.current.restart()

            self.current.volume = self.volume
            self.voice.play(self.current, after=self.play_next_song)
            # await self.current.channel.send(embed=self.current.create_embed())
            if self.dnd_playlist and not self.loop:
                self.bot.loop.create_task(self.dnd_random_song())

            await self.play_next.wait()

    def play_next_song(self, error=None):
        if error:
            raise Exception(str(error))
            # raise error
        self.play_next.set()

    async def stop(self, disconnect=True):
        self.queue.clear()

        if self.voice and disconnect:
            await self.voice.disconnect()
            self.voice = None
        self.removed = True

    def skip(self):
        self.loop = False
        if self.is_playing and self.voice:
            self.voice.stop()

    async def dnd_random_song(self, add=True):
        song = await Song.create_source(None, random.choice(
            playlists[self.dnd_playlist]), loop=self.bot.loop)
        if add:
            await self.queue.add(song)
        else:
            return song

    def reset_player(self):
        self.audio_player.cancel()
        self.audio_player = bot.loop.create_task(self.player_task())


class Action:
    def __init__(self, label: str = None, emoji: str = None, function=None, args: list = [], kwargs: dict = {}, style: int = ButtonStyle.gray):
        self.style = style
        self.label = label
        self.emoji = emoji
        self.function = function
        self.args = args
        self.kwargs = kwargs


async def smart_send(ctx, *args, do_not_edit=False, **kwargs):
    if isinstance(ctx, ComponentContext) and not do_not_edit:
        if not 'content' in kwargs:
            if len(args) == 0:
                if not 'delete_after' in kwargs:
                    kwargs['delete_after'] = 10
                await ctx.send(*args, **kwargs)
                return
            kwargs['content'] = args[0]
        await ctx.edit_origin(content=kwargs['content'])
    else:
        await ctx.send(*args, **kwargs)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}

    def get_voice_client(self, ctx: commands.Context) -> VoiceClient:
        client = self.voice_clients.get(ctx.guild.id)
        if not client:
            client = VoiceClient(self.bot)
            self.voice_clients[ctx.guild.id] = client
        if client.removed:
            del client
            client = VoiceClient(self.bot)
            self.voice_clients[ctx.guild.id] = client
        return client

    async def ensure_voice_state(self, ctx: commands.Context, voice_client: VoiceClient) -> bool:
        if not ctx.author.voice:
            await smart_send(ctx, 'Для использования этой команды нужно находиться в голосовом канале')
            return False

        if not ctx.author.voice.channel:
            await smart_send(ctx, 'Для использования этой команды нужно находиться в голосовом канале')
            return False

        if voice_client:
            if voice_client.voice:
                if voice_client.voice.channel and voice_client.voice.channel != ctx.author.voice.channel:
                    await smart_send(ctx, 'Бот уже используется в другом голосовом канале')
                    return False
        return True

    @staticmethod
    def is_dj(member: discord.Member) -> bool:
        for role in member.roles:
            if role.name.lower() == "dj":
                return True
        return Music.is_admin(member)

    @staticmethod
    def is_admin(member: discord.Member) -> bool:
        return member.guild_permissions.administrator

    @cog_ext.cog_slash(name='join', description='Призвать бота в голосовой канал')
    async def join(self, ctx: SlashContext):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        destination = ctx.author.voice.channel
        if voice_client.voice:
            await voice_client.voice.move_to(destination)
        else:
            voice_client.voice = await destination.connect()

    @cog_ext.cog_slash(name='play', description='Включить музыку',
                       options=[
                           create_option(
                               name='search',
                               description='Название или ссылка, если не указанно - ставит плеер на паузу',
                               option_type=3,
                               required=True
                           )
                       ])
    async def play(self, ctx: SlashContext, search: str):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.voice:
            await ctx.invoke(self.join)

        # if search is None:
        #    await ctx.invoke(self.pause)
        #    return
        if voice_client.voice:
            await ctx.defer()
            try:
                song = await Song.create_source(ctx, search, loop=self.bot.loop)
            except SongException as e:
                await smart_send(ctx, str(e))
            else:
                if isinstance(song, list):
                    if len(song) > 1:
                        await voice_client.queue.add(song)
                        await smart_send(ctx, f'{len(song)} треков добавлено в очередь')
                        return
                    elif len(song) == 1:
                        song = song[0]
                    else:
                        return
                await voice_client.queue.add(song)
                await smart_send(ctx, f'Трек {song} добавлен в очередь')

    @cog_ext.cog_slash(name='stop', description='Выключить музыку')
    async def stop(self, ctx: commands.Context):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        await voice_client.stop()
        del voice_client
        await smart_send(ctx, 'Проигрывание остановленно')

    @cog_ext.cog_slash(name='skip', description='Пропустить трек')
    async def skip(self, ctx: commands.Context):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.is_playing:
            return await smart_send(ctx, 'В данный момент нечего скипать')

        voter = ctx.author
        if self.is_dj(voter):
            await smart_send(ctx, 'Трек пропущен диджеем')
            voice_client.skip()
        elif voter == voice_client.current.requester:
            await smart_send(ctx, 'Трек пропущен заказчиком')
            voice_client.skip()
        elif voter.id not in voice_client.current.skip_votes:
            voice_client.current.skip_votes.add(voter.id)
            total_votes = len(voice_client.current.skip_votes)
            listeners = len(ctx.author.voice.channel.members)-1
            need_votes = listeners//2

            if total_votes >= need_votes:
                await smart_send(ctx, 'Трек пропущен')
                voice_client.skip()
            else:
                await smart_send(ctx, f'Голос учтен, всего голосов: **{total_votes}/{need_votes}**')
        else:
            await smart_send(ctx, 'Ты уже голосовал за пропуск этой песни')

    @cog_ext.cog_slash(name='shuffle', description='Перемешать очередь')
    async def shuffle(self, ctx: commands.Context):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if len(voice_client.queue) == 0:
            return await smart_send(ctx, 'Очередь пуста')

        voice_client.queue.shuffle()
        await smart_send(ctx, 'Очередь перемешана')

    @cog_ext.cog_slash(name='loop', description='Включить/выключить повторение трека')
    async def loop(self, ctx: commands.Context):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.is_playing:
            return await smart_send(ctx, 'В данный момент ничего не играет')

        voice_client.loop = not voice_client.loop
        await smart_send(ctx, f'Теперь трек {"не "*int(not voice_client.loop)}будет повторяться')

    @cog_ext.cog_slash(name='playing', description='Отобразить название трека, который сейчас играет')
    async def now(self, ctx: commands.Context):
        voice_client = self.get_voice_client(ctx)
        if voice_client.current:
            await smart_send(ctx, embed=voice_client.current.create_embed())
        else:
            await smart_send(ctx, 'В данный момент ничего не играет')

    @cog_ext.cog_slash(name='pause', description='Поставить плеер на паузу или снять с неё')
    async def pause(self, ctx: commands.Context):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if voice_client.is_playing and voice_client.voice:
            if voice_client.voice.is_playing():
                await smart_send(ctx, 'Плеер поставлен на паузу')
                voice_client.voice.pause()
            else:
                await smart_send(ctx, 'Плеер снят с паузы')
                voice_client.voice.resume()
        else:
            await smart_send(ctx, 'В данный момент ничего не играет')

    @cog_ext.cog_slash(name='queue', description='Отобразить очередь',
                       options=[
                           create_option(
                               name='page',
                               description='Страница (на одной странице 10 песен)',
                               option_type=4,
                               required=False
                           )
                       ])
    async def queue(self, ctx: SlashContext, page: int = 1):
        voice_client = self.get_voice_client(ctx)

        if len(voice_client.queue) == 0:
            return await smart_send(ctx, 'Очередь пуста')

        items_per_page = 10
        pages = math.ceil(len(voice_client.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(voice_client.queue[start:end], start=start):
            queue += f'`{i+1}.` [**{song.title}**]({song.url})\n'

        embed = (discord.Embed(description=f'**{len(voice_client.queue)} треков:**\n\n{queue}')
                 .set_footer(text=f'Страница {page}/{pages}'))
        await smart_send(ctx, embed=embed)

    @cog_ext.cog_slash(name='volume', description='Установить громкость бота',
                       options=[
                           create_option(
                               name='volume',
                               description='Громкость (в %)',
                               option_type=4,
                               required=True
                           )
                       ])
    async def volume(self, ctx: SlashContext, volume: int):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        voice_client.volume = volume / 100
        if voice_client.current:
            voice_client.current.volume = volume / 100
        await smart_send(ctx, f'Громкость установленна на **{volume}%**')

    @cog_ext.cog_slash(name='actions', description='Получить список быстрых действий')
    async def actions(self, ctx: SlashContext):
        if self.is_admin(ctx.author):
            await smart_send(ctx, 'Быстрые действия', components=dnd_action_list)
        else:
            await smart_send(ctx, 'Быстрые действия', components=action_list)

    async def dnd_music(self, ctx: ComponentContext):
        if not self.is_admin(ctx.author):
            await smart_send(ctx, 'Эта панель только для админов, не тыкай ¯\\_(ツ)_/¯', hidden=True, do_not_edit=True)
            return

        voice_client = self.get_voice_client(ctx)

        action = ctx.custom_id
        if action == 'exit':
            if voice_client.dnd_playlist:
                voice_client.dnd_playlist = None
                voice_client.queue = voice_client.queue_before_dnd
                voice_client.skip()
                voice_client.queue_before_dnd = None
                await smart_send(ctx, 'DnD mode deactivated')
            else:
                await smart_send(ctx, 'DnD mode is already deactivated')
            return

        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.voice:
            await self.join.invoke(ctx)

        ac = ''
        if not voice_client.dnd_playlist:
            voice_client.queue_before_dnd = await voice_client.queue.copy()
            ac = "DnD mode activated & "
        await smart_send(ctx, f'{ac}Selected playlist "{action}"')

        voice_client.dnd_playlist = action
        voice_client.queue.clear()
        song = await voice_client.dnd_random_song(add=False)
        voice_client.skip()
        await voice_client.queue.add(song)
        await voice_client.dnd_random_song()


@bot.event
async def on_component(ctx: ComponentContext):
    if isinstance(ctx, ComponentContext):
        # await ctx.defer(hidden=True)
        if ctx.custom_id in list(ACTIONS.keys()):
            if ACTIONS[ctx.custom_id].function:
                function = getattr(music, ACTIONS[ctx.custom_id].function)
                if isinstance(function, CogBaseCommandObject):
                    await function.invoke(ctx)
                else:
                    await function(ctx)


@bot.event
async def on_slash_command_error(ctx: SlashContext, exception):
    if isinstance(exception, discord.ext.commands.errors.MissingPermissions):
        await smart_send(ctx, f'Не хватает полномочий для использования данной команды.')
    else:
        raise exception
    # await smart_send(ctx,f'Произошла ошибка: {error}')


NORMAL_ACTIONS = {
    'pause': Action(style=ButtonStyle.blue, emoji='⏯', function='pause'),
    'skip': Action(style=ButtonStyle.blue, emoji='⏭', function='skip'),
    'stop': Action(style=ButtonStyle.blue, emoji='⏹', function='stop'),
    'loop': Action(style=ButtonStyle.blue, emoji='🔁', function='loop'),
    'now': Action(style=ButtonStyle.blue, emoji='🎶', function='now'),
    'queue': Action(style=ButtonStyle.blue, emoji='📃', function='queue'),
}
DND_ACTIONS = {
    'spooky': Action(emoji='👻', function='dnd_music'),
    'medieval': Action(emoji='🏰', function='dnd_music'),
    'forest': Action(emoji='🌲', function='dnd_music'),
    'magical': Action(emoji='✨', function='dnd_music'),
    'relaxing': Action(emoji='😊', function='dnd_music'),
    'exit': Action(emoji='🚫', function='dnd_music'),
}
ACTIONS = {**NORMAL_ACTIONS, **DND_ACTIONS}
action_list = create_actions(NORMAL_ACTIONS)
dnd_action_list = action_list + create_actions(DND_ACTIONS)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    setup_slash()
    setup_aliases({'stop': ['disconnect'], 'play': ['p'], 'join': [
                  'summon'], 'playing': ['current', 'now'], 'pause': ['resume'], 'loop': ['repeat']})
    await slash.sync_all_commands()
    print('Setup compleated')


@bot.event
async def on_guild_join(guild: discord.Guild):
    setup_slash()
    await slash.sync_all_commands()

music = Music(bot)
bot.add_cog(music)

if __name__ == '__main__':
    with open('token.txt', 'r') as f:
        token = f.read()
else:
    with open('../test-token.txt', 'r') as f:
        token = f.read()
bot.run(token)
