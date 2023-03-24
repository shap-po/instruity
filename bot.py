import asyncio
import os
import discord
from discord.ext import commands

from cogs import MusicCog

intents = discord.Intents.default()
bot = commands.Bot('-', intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.tree.sync()
    print('Synced commands tree')


async def main(token: str):
    music_cog = MusicCog(bot)
    await bot.add_cog(music_cog)
    await bot.start(token)

token = os.environ.get('TOKEN')
if not token:
    try:
        with open('token.txt', 'r') as f:
            token = f.read()
    except FileNotFoundError:
        print('Token not found. Either set the TOKEN environment variable or create a file called "token.txt" with the token in it.')
        exit(1)
asyncio.run(main(token))
