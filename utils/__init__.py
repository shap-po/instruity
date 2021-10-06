import typing
from discord_slash import ComponentContext
from discord.ext.commands import Context
from discord import Member

from utils.setup import *
from utils.actions import *


async def smart_send(ctx: typing.Union[Context, ComponentContext], *args, do_not_edit=False, **kwargs):
    if isinstance(ctx, ComponentContext) and not do_not_edit:
        if not 'content' in kwargs:
            if len(args) == 0:
                if not 'delete_after' in kwargs:
                    kwargs['delete_after'] = 10
                await ctx.send(*args, **kwargs)
                return
            kwargs['content'] = args[0]
        await ctx.edit_origin(content=kwargs['content'])
    else:
        await ctx.send(*args, **kwargs)


def is_admin(member: Member) -> bool:
    return member.guild_permissions.administrator
