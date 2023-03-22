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

if __name__ == '__main__':
    token = os.environ['TOKEN']
else:
    with open('../test-token.txt', 'r') as f:
        token = f.read()
asyncio.run(main(token))
