import asyncio
import os
import discord
from discord.ext import commands

from cogs import MusicCog


class Bot(commands.Bot):
    def __init__(self, token: str, **kwargs):
        if not kwargs.get('command_prefix'):
            kwargs['command_prefix'] = '!'
        if not kwargs.get('intents'):
            kwargs['intents'] = discord.Intents.default()

        super().__init__(**kwargs)
        self.token = token

    async def wrapped_connect(self):
        await self.add_cog(MusicCog(self))
        await self.login(self.token)
        try:
            await self.connect()
        except Exception as e:
            await self.close()

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        await self.tree.sync()


if __name__ == '__main__':
    tokens = os.environ.get('TOKENS') or os.environ.get('TOKEN')
    if not tokens:
        try:
            with open('tokens.txt', 'r') as f:
                tokens = f.read()
        except FileNotFoundError:
            print('Tokens not found. Either set the TOKENS environment variable or create a file called "tokens.txt" with the tokens separated by spaces or newlines.')
            exit(1)
    tokens = tokens.split()
    bots = [Bot(token) for token in tokens]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(
        *[bot.wrapped_connect() for bot in bots]))
    loop.run_forever()
