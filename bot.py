import os
import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext, ComponentContext

from ext import *
from ext.actions import controls_list, infinite_action_list, saved_action_list, opening_action_list
from utils import *

bot = commands.Bot('-')
slash = SlashCommand(bot)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    setup_slash(bot, slash)
    #setup_aliases(slash, {'stop': ['disconnect'], 'playing': ['now'], 'pause': ['resume'], 'loop': ['repeat']})
    await slash.sync_all_commands()
    print('Setup compleated')


@bot.event
async def on_guild_join(guild: discord.Guild):
    setup_slash(bot, slash)
    await slash.sync_all_commands()


@bot.event
async def on_slash_command_error(ctx: SlashContext, exception):
    if isinstance(exception, discord.ext.commands.errors.MissingPermissions):
        await smart_send(ctx, f'Не хватает полномочий для использования данной команды.')
    else:
        raise exception


@bot.event
async def on_component(ctx: ComponentContext):
    """When someone clicks the button - try to run bot actions."""
    await run_actions(ctx, actions)


music_cog = MusicCog(bot)
bot.add_cog(music_cog)
actions_cog = ActionsCog(music_cog)
bot.add_cog(actions_cog)
opening_cog = OpeningCog(bot, music_cog)
bot.add_cog(opening_cog)

for action in list(controls_list.values()):
    action.cog = music_cog

for action in list(infinite_action_list.values())+list(saved_action_list.values()):
    action.cog = actions_cog

for action in list(opening_action_list.values()):
    action.cog = opening_cog

actions = {**controls_list, **infinite_action_list,
           **saved_action_list, **opening_action_list}

if __name__ == '__main__':
    token = os.environ['TOKEN']
else:
    with open('../test-token.txt', 'r') as f:
        token = f.read()
bot.run(token)
