import typing
from discord_slash import ComponentContext
from discord_slash.dpy_overrides import ComponentMessage
from discord_slash.model import SlashMessage
from discord.ext.commands import Context
from discord import Member

from utils.setup import *
from utils.actions import *


async def smart_send(ctx: typing.Union[Context, ComponentContext], *args, do_not_edit=False, **kwargs) -> typing.Optional[typing.Union[SlashMessage, ComponentMessage]]:
    """Send message or edit origin. Better version of something like:

    if isinstance(ctx, Context):
        await ctx.send(msg)
    else:
        await ctx.edit_origin(msg)
    """
    if isinstance(ctx, ComponentContext) and not do_not_edit:
        if not 'content' in kwargs:
            if len(args) == 0:
                if not 'delete_after' in kwargs:
                    kwargs['delete_after'] = 10
                return await ctx.send(*args, **kwargs)
            kwargs['content'] = args[0]
        await ctx.edit_origin(content=kwargs['content'])
        return ctx.origin_message
    else:
        return await ctx.send(*args, **kwargs)


def is_admin(member: Member) -> bool:
    return member.guild_permissions.administrator
