import typing
from discord.ext.commands import Context
from discord_slash.context import ComponentContext
from discord_slash.model import ButtonStyle, CogBaseCommandObject
from discord_slash.utils.manage_components import create_actionrow, create_button


class Action:
    def __init__(self, label: str = None, emoji: str = None, function=None, args: list = [], kwargs: dict = {}, style: int = ButtonStyle.gray):
        self.style = style
        self.label = label
        self.emoji = emoji
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.cog = None


def create_actions(actions: typing.Dict[str, Action], elements_in_row: int = 3) -> list:
    if elements_in_row > 5:
        elements_in_row = 5
    action_list = []
    i = 0
    while i < len(actions):
        row = []
        for _ in range(elements_in_row):
            if i < len(actions):
                id = list(actions.keys())[i]
                action = list(actions.values())[i]
                row.append(create_button(style=action.style,
                           label=action.label, emoji=action.emoji, custom_id=id))
            i += 1
        action_list.append(create_actionrow(*row))
    return action_list


async def run_actions(ctx: typing.Union[Context, ComponentContext], actions: typing.Dict[str, Action]):
    if isinstance(ctx, ComponentContext):
        if ctx.custom_id in list(actions.keys()):
            if actions[ctx.custom_id].function:
                function = getattr(
                    actions[ctx.custom_id].cog, actions[ctx.custom_id].function)
                if isinstance(function, CogBaseCommandObject):
                    await function.invoke(ctx, *actions[ctx.custom_id].args, **actions[ctx.custom_id].kwargs)
                else:
                    await function(ctx, *actions[ctx.custom_id].args, **actions[ctx.custom_id].kwargs)
