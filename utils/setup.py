from discord.ext import commands
from discord_slash import SlashCommand
from copy import copy


def setup_slash(bot: commands.Bot, slash: SlashCommand):
    guild_ids = [guild.id for guild in bot.guilds]
    for command in list(slash.commands.keys()):
        if command == 'context':
            continue
        slash.commands[command].allowed_guild_ids = guild_ids
    for command in list(slash.subcommands.keys()):
        for subcommand in list(slash.subcommands[command].keys()):
            slash.subcommands[command][subcommand].allowed_guild_ids = guild_ids


def setup_aliases(slash: SlashCommand, aliases: dict):
    for command in list(slash.commands.keys()):
        if command == 'context':
            continue
        if command in aliases and command in slash.commands:
            for alias in aliases[command]:
                slash.commands[alias] = slash.commands[command]
                slash.commands[alias].name = alias


def create_alias(func, name):
    func = copy(func)
    func.name = name
    return func
