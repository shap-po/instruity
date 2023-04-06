from discord import Member
import discord


async def smart_send(interaction: discord.Interaction, *args, **kwargs) -> None:
    """Universal function to send messages to channel or edit original response."""
    # if interaction is a button - send message which will be deleted after 10 seconds
    # if id starts with play_again_ - treat it as a regular command
    if interaction.data and interaction.data.get('custom_id') and not interaction.data.get('custom_id').startswith('play_again_'):
        await interaction.channel.send(*args, **kwargs, delete_after=10)
        if not interaction.response.is_done():
            await interaction.response.send_message()  # mark interaction as complete
        return

    if interaction.response.is_done():
        await interaction.edit_original_response(*args, **kwargs)
    else:
        await interaction.response.send_message(*args, **kwargs)


def is_admin(member: Member) -> bool:
    return member.guild_permissions.administrator
