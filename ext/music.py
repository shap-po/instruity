import math
import asyncio
import functools
import typing
import discord
import itertools
import random
import youtube_dl
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option
from async_timeout import timeout

from playlists import playlists
from utils import smart_send, is_admin

DEFAULT_VOLUME = 0.35


youtube_dl.utils.bug_reports_message = lambda: ''


class SongException(Exception):
    """A custom exception for Song.create_source."""


class SongQueue(asyncio.Queue):
    """A song queue object."""

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


class Song(discord.PCMVolumeTransformer):
    """An object that contains basic info about song and can be used in player as music source."""
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

    def __init__(self, requester: discord.Member, data: dict, volume: float = DEFAULT_VOLUME, infinite: bool = False):
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.url = data.get('webpage_url')
        self.stream_url = data.get('url')
        self.requester = requester
        self.skip_votes = set()
        self.infinite = infinite
        self.volume = volume

        self.restart()

    def __str__(self):
        return f'**{self.title}** от **{self.uploader}**'

    @classmethod
    async def create_source(cls, search: str, requester: discord.Member, loop: asyncio.BaseEventLoop = None, infinite: bool = False) -> typing.Union['Song', typing.List['Song']]:
        """Create a new song source from a search.

        Args:
            search (str): URL or song name.
            requester (discord.Member): Requester of the song.
            loop (asyncio.BaseEventLoop, optional): Event loop for searching the song. Defaults to None.
            infinite (bool, optional): Is the song created by infinite playlist mode. Defaults to False.

        Raises:
            SongException: Raised when can't find song.

        Returns:
            :class:`Song` | list[:class:`Song`]
        """

        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(
            cls.ytdl.extract_info, search, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise SongException(
                f'Не удалось получить аудио по запросу: "{search}"')

        if 'entries' not in processed_info:
            info = processed_info
        else:
            playlist = []
            for entry in processed_info['entries']:
                if entry:
                    playlist.append(entry)

            if len(playlist) == 0:
                raise SongException(
                    f'Не удалось найти ничего по запросу: "{search}"')

            return [cls(requester, data=info, infinite=infinite) for info in playlist]

        return cls(requester, data=info, infinite=infinite)

    def restart(self) -> None:
        """Restart the song source to continue playback in loop mode."""
        super().__init__(discord.FFmpegPCMAudio(
            self.stream_url, **self.FFMPEG_OPTIONS), self.volume)

    @staticmethod
    def parse_duration(duration: int) -> str:
        """Parse duration into a string.

        Args:
            duration (int)

        Returns:
            str: Formated duration.
        """
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

    def create_embed(self) -> discord.Embed:
        """Create an embed for `/now` command.

        Returns:
            discord.Embed
        """
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
    """Music player instance."""

    def __init__(self, bot: commands.Bot, volume: float = DEFAULT_VOLUME):
        self.bot = bot

        self.voice = None
        self.queue = SongQueue()
        self.current: Song = None
        self.play_next = asyncio.Event()

        self.loop = False
        self.volume = volume
        self.removed = False

        self.infinite_playlist = None
        self.infinite_queue = SongQueue()

        self.play_now = None

        self.audio_player = bot.loop.create_task(self.player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def is_playing(self) -> bool:
        return self.voice and self.current

    async def player_task(self):
        """An actual player."""
        while True:
            self.play_next.clear()

            if not self.loop:
                try:
                    async with timeout(180):  # 3 minutes
                        if self.play_now:
                            self.current = self.play_now
                            self.play_now = None
                        elif self.infinite_playlist and not len(self.queue):
                            self.current = await self.infinite_queue.get()
                        else:
                            self.current = await self.queue.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return
            else:
                self.current.restart()

            self.current.volume = self.volume
            self.voice.play(self.current, after=self.play_next_song)

            if self.infinite_playlist and not self.loop and self.current.infinite:
                self.bot.loop.create_task(self.random_infinite_song())

            await self.play_next.wait()

    def play_next_song(self, error=None):
        """This function will force player to play next song.
        It automatically runs when previous song ends.
        """
        if error:
            raise Exception(str(error))
            # raise error
        if not self.loop:
            self.current = None
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

    async def random_infinite_song(self, add=True) -> typing.Optional[Song]:
        """Create a :class:`Song` using random url from selected infinite playlist.

        Args:
            add (bool, optional): Add created song to `infinite_queue`. Defaults to True.

        Returns:
            Optional[Song]
        """
        while True:
            try:
                song = await Song.create_source(search=random.choice(playlists[self.infinite_playlist]), requester=self.bot.user, loop=self.bot.loop, infinite=True)
            except Exception as exception:
                print(f'Random infinite song error: {exception=}')
            else:
                break

        if add:
            await self.infinite_queue.add(song)
        else:
            return song

    def reset_player(self) -> None:
        self.audio_player.cancel()
        self.audio_player = self.bot.loop.create_task(self.player_task())

    async def play(self, song: Song):
        if not len(self.queue):
            if self.current:
                self.skip()
            await self.queue.add(song)
        else:
            self.play_now = song
            self.skip()


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}

    def get_voice_client(self, ctx: SlashContext) -> VoiceClient:
        """Get a voice client or create a new one."""
        client = self.voice_clients.get(ctx.guild.id)
        if not client:
            client = VoiceClient(self.bot)
            self.voice_clients[ctx.guild.id] = client
        if client.removed:
            del client
            client = VoiceClient(self.bot)
            self.voice_clients[ctx.guild.id] = client
        return client

    async def ensure_voice_state(self, ctx: SlashContext, voice_client: VoiceClient) -> bool:
        """Ensure that the voice state is valid.
        If not, parrent function should stop it's execution."""

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
        return is_admin(member)

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
                               description='Название или ссылка',
                               option_type=str,
                               required=True
                           )
                       ])
    async def play(self, ctx: SlashContext, search: str):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.voice:
            await ctx.invoke(self.join)

        if voice_client.voice:
            await ctx.defer()
            try:
                song = await Song.create_source(search=search, requester=ctx.author, loop=self.bot.loop)
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

            if voice_client.current:
                if voice_client.current.infinite:
                    voice_client.skip()

    @cog_ext.cog_slash(name='stop', description='Выключить музыку')
    async def stop(self, ctx: SlashContext):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        await voice_client.stop()
        del voice_client
        await smart_send(ctx, 'Проигрывание остановленно')

    @cog_ext.cog_slash(name='skip', description='Пропустить трек')
    async def skip(self, ctx: SlashContext):
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
    async def shuffle(self, ctx: SlashContext):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if len(voice_client.queue) == 0:
            return await smart_send(ctx, 'Очередь пуста')

        voice_client.queue.shuffle()
        await smart_send(ctx, 'Очередь перемешана')

    @cog_ext.cog_slash(name='loop', description='Включить/выключить повторение трека')
    async def loop(self, ctx: SlashContext):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.is_playing:
            return await smart_send(ctx, 'В данный момент ничего не играет')

        voice_client.loop = not voice_client.loop
        await smart_send(ctx, f'Теперь трек {"не "*int(not voice_client.loop)}будет повторяться')

    @cog_ext.cog_slash(name='playing', description='Отобразить название трека, который сейчас играет')
    async def now(self, ctx: SlashContext):
        voice_client = self.get_voice_client(ctx)
        if voice_client.current:
            await smart_send(ctx, embed=voice_client.current.create_embed())
        else:
            await smart_send(ctx, 'В данный момент ничего не играет')

    @cog_ext.cog_slash(name='pause', description='Поставить плеер на паузу или снять с неё')
    async def pause(self, ctx: SlashContext):
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
                               option_type=int,
                               required=False
                           )
                       ])
    async def queue(self, ctx: SlashContext, page: int = 1):
        voice_client = self.get_voice_client(ctx)

        if len(voice_client.queue) == 0:
            await smart_send(ctx, 'Очередь пуста')
            return

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
                               option_type=int,
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

    @cog_ext.cog_slash(name='clear', description='Очистить очередь')
    async def clear(self, ctx: SlashContext):
        voice_client = self.get_voice_client(ctx)
        if not await self.ensure_voice_state(ctx, voice_client):
            return

        voice_client.skip()

        if len(voice_client.queue) == 0:
            await smart_send(ctx, 'Очередь пуста')
            return

        voice_client.queue.clear()
        await smart_send(ctx, 'Очередь очищена')
