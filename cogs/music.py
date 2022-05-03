import math
import asyncio
import functools
import typing
import discord
import itertools
import random
import youtube_dl
from discord.ext import commands
from discord import app_commands
from async_timeout import timeout

from utils import smart_send, is_admin

DEFAULT_VOLUME = 0.35

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

RANDOM_FOOTERS = [
    {'text': 'путін хуйло'},
    {'text': 'Слава Україні!'},
    {'text': 'Російський воєнний корабель - іди нахуй!'},
    {'text': 'J̵̩͗ȗ̴̳s̴̰̍t̵̲́ ̸̤͛M̴̱͝ỏ̵͙n̵̛̦į̵͊k̵̪̾ä̷̜́'},
    {'text': 'паралелепіпед'},
    {'text': 'паляниця'},
    {'text': 'amogus', 'icon_url': 'https://static.wikia.nocookie.net/amogus/images/c/cb/Susremaster.png/revision/latest/scale-to-width-down/1200?cb=20210806124552'},
]
RANDOM_FOOTER_CHANCE = 0.1

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
    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, requester: discord.Member, data: dict, volume: float = DEFAULT_VOLUME):
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.url = data.get('webpage_url')
        self.stream_url = data.get('url')
        self.requester = requester
        self.skip_votes = set()
        self.volume = volume

        self.restart()

    def __str__(self):
        return f'**{self.title}** від **{self.uploader}**'

    @classmethod
    async def create_source(self, search: str, requester: discord.Member, loop: asyncio.BaseEventLoop = None) -> typing.List['Song']:
        """Create a new song source from a search.

        Args:
            search (str): URL or song name.
            requester (discord.Member): Requester of the song.
            loop (asyncio.BaseEventLoop, optional): Event loop for searching the song. Defaults to None.

        Raises:
            SongException: Raised when can't find song.

        Returns:
            :class:`Song` | list[:class:`Song`]
        """

        loop = loop or asyncio.get_event_loop()

        if not search.startswith('https:') and not search.startswith('http:'):
            search = search.replace(':', '')

        partial = functools.partial(
            self.ytdl.extract_info, search, download=False)

        try_count = 0
        while True:
            try:
                processed_info = await loop.run_in_executor(None, partial)
            except:
                if try_count < 2:  # try get song 2 times, otherwise - give exception
                    try_count += 1
                    await asyncio.sleep(0.1)
                    continue
                raise SongException(
                    f'Сталася помилка при отримані треку за запитом "{search}"')
            else:
                break

        if processed_info is None:
            raise SongException(
                f'Не вдалося отримати аудіо за запитом "{search}"')

        if 'entries' in processed_info:
            songs = processed_info['entries']
            if len(songs) == 0:
                raise SongException(
                    f'Не вдалося знайти нічого за запитом "{search}"')
        else:
            songs = [processed_info]

        return [self(requester, data=info) for info in songs]

    def restart(self) -> None:
        """Restart the song source to continue playback in loop mode."""
        super().__init__(discord.FFmpegPCMAudio(
            self.stream_url, **FFMPEG_OPTIONS), self.volume)

    @ staticmethod
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

        output = []
        if days > 0:
            days = str(days)
            if days[-1] == 1 and days[0] != 1:
                output.append(f'{days} день')
            elif days[-1] in '234' and days[0] != 1:
                output.append(f'{days} дні')
            else:
                output.append(f'{days} днів')
        if hours > 0:
            hours = str(hours)
            if hours[-1] == 1 and hours[0] != 1:
                output.append(f'{hours} година')
            elif hours[-1] in '234' and hours[0] != 1:
                output.append(f'{hours} години')
            else:
                output.append(f'{hours} годин')
        if minutes > 0:
            minutes = str(minutes)
            if minutes[-1] == 1 and minutes[0] != 1:
                output.append(f'{minutes} хвилина')
            elif minutes[-1] in '234' and minutes[0] != 1:
                output.append(f'{minutes} хвилини')
            else:
                output.append(f'{minutes} хвилин')
        if seconds > 0:
            seconds = str(seconds)
            if seconds[-1] == 1 and seconds[0] != 1:
                output.append(f'{seconds} секунда')
            elif seconds[-1] in '234' and seconds[0] != 1:
                output.append(f'{seconds} секунди')
            else:
                output.append(f'{seconds} секунд')

        return ' '.join(output)

    def create_embed(self) -> discord.Embed:
        """Create an embed for `/now` command.

        Returns:
            discord.Embed
        """
        embed = (discord.Embed(title=self.title,
                               color=discord.Color.blurple(),
                               url=self.url)
                 .add_field(name='Тривалість', value=self.duration)
                 .add_field(name='Замовив', value=self.requester.mention)
                 .add_field(name='Автор', value=f'[{self.uploader}]({self.uploader_url})')
                 .set_thumbnail(url=self.thumbnail)
                 )
        if random.random() < RANDOM_FOOTER_CHANCE:
            embed.set_footer(**random.choice(RANDOM_FOOTERS))
        return embed


class VoiceClient:
    """Music player instance."""

    def __init__(self, bot: commands.Bot, volume: float = DEFAULT_VOLUME):
        self.bot = bot

        self.voice: discord.voice_client.VoiceClient = None
        self.queue = SongQueue()
        self.current: Song = None
        self.play_next = asyncio.Event()

        self.loop = False
        self.volume = volume
        self.removed = False

        self.audio_player = bot.loop.create_task(self.player_task())

    def __del__(self):
        self.audio_player.cancel()

    @ property
    def is_playing(self) -> bool:
        return self.voice and self.current

    async def player_task(self):
        """An actual player."""
        while True:
            self.play_next.clear()

            if self.loop:
                self.current.restart()
            else:
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.queue.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return

            self.current.volume = self.volume
            self.voice.play(self.current, after=self.play_next_song)

            await self.play_next.wait()

    def play_next_song(self, error=None):
        """This function will force player to play next song.
        It automatically runs when previous song ends.
        """
        if error:
            raise error
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

    def reset_player(self) -> None:
        self.audio_player.cancel()
        self.audio_player = self.bot.loop.create_task(self.player_task())

    async def play(self, song: Song) -> None:
        if self.current:
            self.skip()
        await self.queue.add(song)


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}

        @bot.event
        async def on_interaction(interaction: discord.interactions.Interaction) -> None:
            await self.interaction_listener(interaction)

    def get_voice_client(self, interaction: discord.Interaction) -> VoiceClient:
        """Get a voice client or create a new one."""
        client = self.voice_clients.get(interaction.guild.id)
        if not client:
            client = VoiceClient(self.bot)
            self.voice_clients[interaction.guild.id] = client
        if client.removed:
            del client
            client = VoiceClient(self.bot)
            self.voice_clients[interaction.guild.id] = client
        return client

    async def ensure_voice_state(self, interaction: discord.Interaction, voice_client: VoiceClient) -> bool:
        """Ensure that the voice state is valid.
        If not, parrent function should stop it's execution."""

        if not interaction.user.voice:
            await smart_send(interaction, content='Для використання цієї команди потрібно бути в голосовому каналі')
            return False

        if not interaction.user.voice.channel:
            await smart_send(interaction, content='Для використання цієї команди потрібно бути в голосовому каналі')
            return False

        if voice_client:
            if voice_client.voice:
                if voice_client.voice.channel and voice_client.voice.channel != interaction.user.voice.channel:
                    await smart_send(interaction, content='Бот вже використовується в іншому голосовому каналі')
                    return False
        return True

    async def interaction_listener(self, interaction: discord.Interaction):
        """Listen for interactions and handle them;
        I know I can handle events using decorators in the view, but if I do it that way, after bot restart the bot will not be able to handle previous interactions"""
        custom_id = interaction.data.get('custom_id')
        if custom_id is None:
            return

        if custom_id == 'pause':
            await self.pause(interaction)
        elif custom_id == 'stop':
            await self.stop(interaction)
        elif custom_id == 'skip':
            await self.skip(interaction)
        elif custom_id == 'shuffle':
            await self.shuffle(interaction)
        elif custom_id == 'loop':
            await self.loop(interaction)
        elif custom_id == 'now':
            await self.now(interaction)
        elif custom_id == 'queue':
            await self.queue(interaction)
        elif custom_id == 'clear':
            await self.clear(interaction)

    @ staticmethod
    def is_dj(member: discord.Member) -> bool:
        for role in member.roles:
            if role.name.lower() == "dj":
                return True
        return is_admin(member)

    async def join(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        destination = interaction.user.voice.channel
        if voice_client.voice:
            await voice_client.voice.move_to(destination)
        else:
            voice_client.voice = await destination.connect()

    async def play(self, interaction: discord.Interaction, search: str) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        if not voice_client.voice:
            await self.join(interaction)

        if voice_client.voice:
            await interaction.response.defer(thinking=True)
            try:
                songs = await Song.create_source(search=search, requester=interaction.user, loop=self.bot.loop)
            except SongException as e:
                await smart_send(interaction, content=str(e))
            else:
                if len(songs) > 1:
                    await smart_send(interaction, content=f'{len(songs)} треків додано в чергу')
                elif len(songs) == 1:
                    await smart_send(interaction, content=f'Трек {songs[0]} додано в чергу')
                else:
                    return
                await voice_client.queue.add(songs)

    async def stop(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if voice_client.voice:
            await voice_client.voice.disconnect()

        await voice_client.stop()
        del voice_client
        await smart_send(interaction, content='Музика вимкнена')

    async def skip(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        if not voice_client.is_playing:
            return await smart_send(interaction, content='На даний момент нічого не грає')

        voter = interaction.user
        if self.is_dj(voter):
            await smart_send(interaction, content='DJ пропустив трек')
            voice_client.skip()
        elif voter == voice_client.current.requester:
            await smart_send(interaction, content='Трек пропущено замовником')
            voice_client.skip()
        elif voter.id not in voice_client.current.skip_votes:
            voice_client.current.skip_votes.add(voter.id)
            total_votes = len(voice_client.current.skip_votes)
            listeners = len(interaction.user.voice.channel.members)-1
            need_votes = listeners//2

            if total_votes >= need_votes:
                await smart_send(interaction, content='Трек пропущено')
                voice_client.skip()
            else:
                await smart_send(interaction, content=f'Голос враховано, всього голосів: **{total_votes}/{need_votes}**')
        else:
            await smart_send(interaction, content='Ви вже проголосували за пропуск цієї пісні')

    async def shuffle(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        if len(voice_client.queue) == 0:
            return await smart_send(interaction, content='Черга порожня')

        voice_client.queue.shuffle()
        await smart_send(interaction, content='Черга змішана')

    async def loop(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        if not voice_client.is_playing:
            return await smart_send(interaction, content='На даний момент нічого не грає')

        voice_client.loop = not voice_client.loop
        await smart_send(interaction, content=f'Тепер трек {"не "*int(not voice_client.loop)}буде повторяться')

    async def now(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if voice_client.current:
            await smart_send(interaction, content='Зараз грає', embed=voice_client.current.create_embed())
        else:
            await smart_send(interaction, content='На даний момент нічого не грає')

    async def pause(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        if voice_client.is_playing and voice_client.voice:
            if voice_client.voice.is_playing():
                await smart_send(interaction, content='Плеєр призупинений')
                voice_client.voice.pause()
            else:
                await smart_send(interaction, content='Плеєр знято з паузи')
                voice_client.voice.resume()
        else:
            await smart_send(interaction, content='На даний момент нічого не грає')

    async def queue(self, interaction: discord.Interaction, page: int = 1) -> None:
        voice_client = self.get_voice_client(interaction)

        if len(voice_client.queue) == 0:
            await smart_send(interaction, content='Черга порожня')
            return

        items_per_page = 10
        pages = math.ceil(len(voice_client.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(voice_client.queue[start:end], start=start):
            queue += f'`{i+1}.` [**{song.title}**]({song.url})\n'

        embed = (discord.Embed(description=f'**{len(voice_client.queue)} треків:**\n\n{queue}')
                 .set_footer(text=f'Сторінка {page}/{pages}'))
        await smart_send(interaction, embed=embed)

    async def volume(self, interaction: discord.Interaction, volume: int) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        voice_client.volume = volume / 100
        if voice_client.current:
            voice_client.current.volume = volume / 100
        await smart_send(interaction, content=f'Гучність встановлена на **{volume}%**')

    async def clear(self, interaction: discord.Interaction) -> None:
        voice_client = self.get_voice_client(interaction)
        if not await self.ensure_voice_state(interaction, voice_client):
            return

        voice_client.skip()

        if len(voice_client.queue) == 0:
            await smart_send(interaction, content='Черга порожня')
            return

        voice_client.queue.clear()
        await smart_send(interaction, content='Черга очищена')

    async def actions(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(content='Доступні команди:', view=ActionView())

    # define commands

    @ app_commands.command(name='join', description='Приєднати бота до голосового каналу')
    async def join_cmd(self, interaction: discord.Interaction):
        await self.join(interaction)

    @ app_commands.command(name='play', description='Додати пісню в чергу')
    async def play_cmd(self, interaction: discord.Interaction, search: str):
        await self.play(interaction, search)

    @ app_commands.command(name='stop', description='Вимкнути музику')
    async def stop_cmd(self, interaction: discord.Interaction):
        await self.stop(interaction)

    @ app_commands.command(name='skip', description='Пропустити трек')
    async def skip_cmd(self, interaction: discord.Interaction):
        await self.skip(interaction)

    @ app_commands.command(name='shuffle', description='Перемішати чергу')
    async def shuffle_cmd(self, interaction: discord.Interaction):
        await self.shuffle(interaction)

    @ app_commands.command(name='loop', description='Увімкнути/вимкнути повторення треку')
    async def loop_cmd(self, interaction: discord.Interaction):
        await self.loop(interaction)

    @ app_commands.command(name='now', description='Відобразити назву треку, який зараз відтворюється')
    async def now_cmd(self, interaction: discord.Interaction):
        await self.now(interaction)

    @ app_commands.command(name='pause', description='Поставити музику на паузу')
    async def pause_cmd(self, interaction: discord.Interaction):
        await self.pause(interaction)

    @ app_commands.command(name='queue', description='Відобразити чергу')
    async def queue_cmd(self, interaction: discord.Interaction, page: int = 1):
        await self.queue(interaction, page)

    @ app_commands.command(name='volume', description='Встановіть гучність бота')
    async def volume_cmd(self, interaction: discord.Interaction, volume: int):
        await self.volume(interaction, volume)

    @ app_commands.command(name='clear', description='Очистіть чергу')
    async def clear_cmd(self, interaction: discord.Interaction):
        await self.clear(interaction)

    @ app_commands.command(name='actions', description='Відобразити кнопки')
    async def actions_cmd(self, interaction: discord.Interaction):
        await self.actions(interaction)


class ActionView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.buttons = [
            [
                discord.ui.Button(emoji='⏯', custom_id='pause'),
                discord.ui.Button(emoji='⏹', custom_id='stop'),
                discord.ui.Button(emoji='⏭', custom_id='skip'),
                discord.ui.Button(emoji='🔀', custom_id='shuffle'),
            ],
            [
                discord.ui.Button(emoji='🔂', custom_id='loop'),
                discord.ui.Button(emoji='🎶', custom_id='now'),
                discord.ui.Button(emoji='📋', custom_id='queue'),
                discord.ui.Button(emoji='🧹', custom_id='clear'),
            ],
        ]
        for row, buttons in enumerate(self.buttons):
            for button in buttons:
                button.style = discord.ButtonStyle.blurple
                button.row = row
                self.add_item(button)