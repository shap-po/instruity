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

    @staticmethod
    def get_shared(lists: typing.List[list]) -> typing.List[str]:
        while len(lists) > 1:
            lists[0] = list(set(lists[0]).intersection(lists[1]))
            del lists[1]
        return lists[0]

    async def run_quiz(self, ctx: typing.Union[SlashContext, ComponentContext], userids: typing.List[str], listened: typing.Optional[typing.List[str]] = []):
        voice_client = self.music_cog.get_voice_client(ctx)
        if not await self.music_cog.ensure_voice_state(ctx, voice_client):
            return

        if not voice_client.voice:
            await self.music_cog.join.invoke(ctx)

        anime_list = [self.get_anime(userid) for userid in userids]
        anime_list = self.get_shared(anime_list)
        if len(anime_list) == 0:
            userids = ' '.join(userids)
            await smart_send(ctx, f'Не найдено общих аниме для пользователей: [{userids}]')
            return
        if len(anime_list) == len(listened):
            userids = ' '.join(userids)
            await smart_send(ctx, f'Все опенинги были прослушаны\nИнформация для бота: ||ids: {userids}||')
            return

        full_list = []+anime_list
        for i in sorted(listened, reverse=True):
            del anime_list[i]

        while True:
            anime_link = random.choice(anime_list)
            if not anime_link:
                continue
            anime_name = self.get_name(f'{self.URL}{anime_link}')
            if not anime_name:
                continue

            try:
                song = await Song.create_source(
                    search=f'{anime_name[0]} opening', requester=self.bot.user, loop=self.bot.loop)
            except SongException:
                pass
            except Exception as e:
                print(anime_name[0])
                raise e
            else:
                if isinstance(song, list):
                    song = song[0]
                anime_id = full_list.index(anime_link)
                listened.append(anime_id)
                break

        userids = ' '.join(userids)
        if isinstance(ctx, ComponentContext):  # add empty spoiler to hide anime name
            addition = '' if f'||{ZERO_SPACE}||' in ctx.origin_message.content else f'||{ZERO_SPACE}||'
        else:
            addition = ''
        listened = ' '.join(map(str, listened))
        await smart_send(ctx, f'{addition}Запущен опенинг из аниме ||{anime_name[1]}||\nИнформация для бота: ||ids: {userids}; listened: {listened}||', components=opening_actions)

        await voice_client.play(song)

    @cog_ext.cog_slash(name='opening', description='Включить случайный опенинг (выбираются только аниме, которые смотрели все)',
                       options=[
                           create_option(
                               name='link',
                               description='Ссылка на профиль',
                               option_type=str,
                               required=True
                           ),
                           create_option(
                               name='link2',
                               description='Ссылка на профиль',
                               option_type=str,
                               required=False
                           ),
                           create_option(
                               name='link3',
                               description='Ссылка на профиль',
                               option_type=str,
                               required=False
                           ),
                           create_option(
                               name='link4',
                               description='Ссылка на профиль',
                               option_type=str,
                               required=False
                           ),
                           create_option(
                               name='link5',
                               description='Ссылка на профиль',
                               option_type=str,
                               required=False
                           )
                       ])
    async def opening(self, ctx: SlashContext, **links: typing.Dict[str, str]):
        await ctx.defer()
        userids = self.get_userids(list(links.values()))
        if not len(userids):
            await smart_send(ctx, 'Кривая ссылка, нужно в профиле (https://yummyanime.club/profile) тыкнуть "Ссылка на этот профиль"')
            return
        await self.run_quiz(ctx, userids)

    async def new_opening(self, ctx: ComponentContext):
        await ctx.defer(edit_origin=True)
        search = re.search(r'\|\|ids: ([^\|;]+); listened: ([^\|]+)\|\|',
                           str(ctx.origin_message.content))
        if not search:
            await smart_send(ctx, 'Произошла ошибка')
            return
        userids = search[1].split(' ')
        listened = list(map(int, search[2].split(' ')))

        await self.run_quiz(ctx, userids, listened)
