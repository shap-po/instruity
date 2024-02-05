import asyncio
import os
import discord
from discord.ext import commands

from cogs import MusicCog

from dotenv import load_dotenv
load_dotenv()


class Instruity(commands.Bot):
    def __init__(
        self,
        token: str,
        speciality: str = None,
        **kwargs,
    ):
        super().__init__(**{
            'command_prefix': '!',  # required by discord.py but not used
            'intents': discord.Intents.default(),
            'help_command': None,
            **kwargs
        })
        self.token = token
        self.speciality = speciality

    async def wrapped_connect(self):
        await self.add_cog(MusicCog(self))
        await self.login(self.token)
        try:
            await self.connect()
        except Exception as e:
            await self.close()

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        if os.environ.get('HIDDEN'):
            await self.change_presence(status=discord.Status.invisible)
        else:
            await self.change_presence(status=discord.Status.online)
        await self.tree.sync()


def main():
    tokens = os.environ.get('TOKENS') or os.environ.get('TOKEN')
    specialities = os.environ.get('SPECIALITIES') or os.environ.get('SPECIALITY')
    if not tokens:
        try:
            # left in for backwards compatibility, .env is the preferred method
            with open('tokens.txt', 'r') as f:
                tokens = f.read()
        except FileNotFoundError:
            print('Tokens not found. Either set the TOKENS environment variable or create a .env file with the TOKENS variable.')
            exit(1)
    tokens = tokens.split()

    if specialities:
        specialities = specialities.split()
        if len(specialities) != len(tokens):
            print('Warning: Specialities and tokens are not the same length. Specialities will be ignored.')
            specialities = None
        else:
            specialities = [s if s.lower() not in ('none', 'null', 'nil', '-')
                            else None for s in specialities]
    if not specialities:
        specialities = [None] * len(tokens)

    bots = [Instruity(token, speciality) for token, speciality in zip(tokens, specialities)]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        asyncio.gather(
            *[bot.wrapped_connect() for bot in bots]
        )
    )
    loop.run_forever()


if __name__ == '__main__':
    main()
