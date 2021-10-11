from discord.ext import commands
from discord_slash import SlashContext, ComponentContext, cog_ext
import typing
from bs4 import BeautifulSoup
import re
import cloudscraper
from discord_slash.utils.manage_commands import create_option
import random
import requests

from utils import smart_send
from ext.music import MusicCog, Song, SongException
from .actions import opening_actions
ZERO_SPACE = '​'  # there is a space between quotes, believe me :)


class OpeningList:
    def __init__(self, user_ids: typing.List[str], anime_list: typing.List[str]):
        self.user_ids = user_ids
        self.anime_list = anime_list

    def remove(self, anime: str):
        self.anime_list.remove(anime)

    def random(self) -> str:
        return random.choice(self.anime_list)

    def __len__(self) -> int:
        return len(self.anime_list)

    def is_empty(self) -> bool:
        return not bool(len(self))


class OpeningCog(commands.Cog):
    session = requests.session()
    session.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
         (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'}
    scraper = cloudscraper.create_scraper(sess=session)
    URL = 'https://yummyanime.info/'

    if URL.endswith('/'):
        URL = URL[:-1]

    def __init__(self, bot: commands.Bot, music_cog: MusicCog):
        self.music_cog = music_cog
        self.bot = bot
        self.openings: typing.Dict[int, OpeningList] = {}

    @staticmethod
    def get_userids(links: typing.List[str]) -> typing.List[str]:
        userids = []
        for link in links:
            userid = re.search(r'id\d+', link)
            if userid:
                userids.append(userid[0])
        return userids

    def get_anime(self, userid: str) -> typing.List[str]:
        r = self.scraper.get(
            f'{self.URL}/users/{userid}?tab=watched')
        s = BeautifulSoup(r.text, 'html.parser')
        return [i['href'] for i in s.findAll('a', href=True) if '/catalog/item/' in i['href']]

    def get_name(self, link: str) -> typing.List[str]:
        """Get anime name

        Args:
            link (str): link to yummyanime

        Returns:
            list[str] | None: list of two elements, first - english ot japanise name, second - russian; None if anime is not series one or can't find name
        """
        r = self.scraper.get(link)
        s = BeautifulSoup(r.text, 'html.parser')
        type = [i.text for i in s.findAll(
            'ul', class_='content-main-info')[0].findAll('li') if 'Тип:' in i.text]
        if type:
            type = type[0][5:]
        if not type == 'Сериал':
            return None

        names = [i.text for i in s.findAll(
            'ul', class_='alt-names-list')[0].findAll('li') if not i.text == 'Показать ещё']
        index = 0
        while index < len(names):
            if any(x in names[index] for x in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
                del names[index]
            else:
                index += 1
        if not names:
            return None

        ru_name = [i.text for i in s.findAll('h1')][0]
        ru_name = re.search(r'\s*(.+)\s*', ru_name)[1]
        name = [names[0], ru_name]

        return name

    def get_openings(self, id: int) -> typing.Optional[OpeningList]:
        return self.openings.get(id)

    @staticmethod
    def get_shared(lists: typing.List[list]) -> typing.List[str]:
        while len(lists) > 1:
            lists[0] = set(lists[0]).intersection(lists[1])
            del lists[1]
        return list(lists[0])

    @staticmethod
    def get_all(lists: typing.List[list]) -> typing.List[str]:
        return list({item for sublist in lists for item in sublist})

    async def run_quiz(self, ctx: typing.Union[SlashContext, ComponentContext], userids: typing.Optional[typing.List[str]] = None, shared_only: typing.Optional[bool] = True, repeat: typing.Optional[bool] = False):
        voice_client = self.music_cog.get_voice_client(ctx)
        if not await self.music_cog.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.voice:
            await self.music_cog.join.invoke(ctx)

        str_userids = ' '.join(userids)
        bot_info = f'\nИнформация для бота: ||ids: {str_userids}; shared: {int(shared_only)}; repeat: {int(repeat)}||'

        if isinstance(ctx, ComponentContext):
            opening_list = self.get_openings(ctx.origin_message.id)
        else:
            opening_list = None
        if opening_list is None:
            if not userids:
                await smart_send(ctx, f'К сожалению, эта кнопка больше не работает, команду придется использовать снова.')
                return
            anime_list = [self.get_anime(userid) for userid in userids]
            if not all(anime_list):
                userids = ' '.join(userids)
                await smart_send(ctx, f'Один из пользователей не смотрит аниме :({bot_info}')
                return
            if shared_only:
                anime_list = self.get_shared(anime_list)
            else:
                anime_list = self.get_all(anime_list)
            if not len(anime_list):
                userids = ' '.join(userids)
                await smart_send(ctx, f'Не найдено общих аниме для выбранных пользователей{bot_info}')
                return
            opening_list = OpeningList(userids, anime_list)

        while True:
            if opening_list.is_empty():
                await smart_send(ctx, f'Все опенинги были прослушаны, если хотите чтоб они повторялись - укажите "repeat=True"{bot_info}', components=opening_actions)
                try:
                    del self.openings[ctx.origin_message.id]
                except:
                    pass
                return
            anime_link = opening_list.random()
            if not anime_link:
                continue
            anime_name = self.get_name(f'{self.URL}{anime_link}')
            if not anime_name:
                opening_list.remove(anime_link)
                continue

            try:
                song = await Song.create_source(
                    search=f'{anime_name[0]} opening', requester=self.bot.user, loop=self.bot.loop)
            except SongException:
                opening_list.remove(anime_link)
            except Exception as e:
                print(anime_name[0])
                raise e
            else:
                if isinstance(song, list):
                    song = song[0]
                if not repeat:
                    opening_list.remove(anime_link)
                break

        userids = ' '.join(userids)
        if isinstance(ctx, ComponentContext):  # add empty spoiler to hide anime name
            spoiler = '' if f'||{ZERO_SPACE}||' in ctx.origin_message.content else f'||{ZERO_SPACE}||'
        else:
            spoiler = ''
        message = await smart_send(ctx, f'{spoiler}Запущен опенинг из аниме ||{anime_name[1]}||{bot_info}', components=opening_actions)
        self.openings[message.id] = opening_list
        await voice_client.play(song)

    @cog_ext.cog_slash(name='opening', description='Включить случайный опенинг',
                       options=[
                           create_option(
                               name='links',
                               description='Одна или более ссылка на профиль, разделенные пробелами',
                               option_type=str,
                               required=True
                           ),
                           create_option(
                               name='shared_only',
                               description='Включать только опенинги к аниме, которые смотрели все',
                               option_type=bool,
                               required=False
                           ),
                           create_option(
                               name='repeat',
                               description='Могут ли опенинги повторяться',
                               option_type=bool,
                               required=False
                           )
                       ])
    async def opening(self, ctx: SlashContext, links: str, shared_only: bool = True, repeat: bool = False):
        await ctx.defer()
        userids = self.get_userids(links.split(' '))
        if not len(userids):
            await smart_send(ctx, 'Кривая ссылка, нужно в профиле (https://yummyanime.club/profile) тыкнуть "Ссылка на этот профиль"')
            return
        await self.run_quiz(ctx, userids, shared_only, repeat)

    async def new_opening(self, ctx: ComponentContext):
        await ctx.defer(edit_origin=True)
        content = r'([^\|;]+)'
        search = re.search(rf'\|\|ids: {content}; shared: {content}; repeat: {content}\|\|',
                           str(ctx.origin_message.content))

        if search:
            userids = search[1].split(' ')
            shared_only = bool(int(search[2]))
            repeat = bool(int(search[3]))
        else:
            userids = None
            shared_only = True
            repeat = False

        await self.run_quiz(ctx, userids, shared_only, repeat)
