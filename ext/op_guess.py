from discord.ext import commands
from discord_slash import SlashContext, ComponentContext, cog_ext

from utils import smart_send
from ext.music import MusicCog


class OpGuessCog(commands.Cog):
    def __init__(self, bot: commands.Bot, music_cog: MusicCog):
        self.bot = bot
        self.music_cog = music_cog

    '''@cog_ext.cog_slash(name='actions', description='Получить список быстрых действий')
    async def actions(self, ctx: SlashContext):
        await smart_send(ctx, 'Быстрые действия', components=full_actions)'''
