import discord
from discord.ext import commands
import asyncio
import main

database = main.database


class Moderation:

    def __init__(self, client):
        self.client = client

    @commands.command(aliases=["Ban"])
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, mention=None):
        if mention is None:
            await ctx.send("Give me a user to mute!")

        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        await ctx.guild.ban(user, delete_message_days=0)
        await ctx.send(f"Banned {user.mention} ({user.id})")

    @commands.command(aliases=["Sinbin", "mute", "Mute"])
    @commands.has_permissions(administrator=True)
    async def sinbin(self, ctx, mention=None, time=None):
        role_id = database.get_attr("data", [str(ctx.guild.id), "roles", "muterole"], 0)
        muterole = ctx.message.guild.get_role(role_id)
        if muterole is None:
            await ctx.send(f"Muterole for this server is invalid or not set, please use -rolesetup muterole")
            return

        if mention is None:
            await ctx.send("Give me a user to mute!")

        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        if time is not None:
            try:
                time = int(time)
            except ValueError:
                await ctx.send(f"Invalid timeframe `{time}`. Please give time in minutes")
                return

        await user.add_roles(muterole)
        await ctx.send(f"Muted {user.mention}" + (f" for {time} minutes" if time is not None else ""))

        if time is not None:
            await asyncio.sleep(time * 60)
            if muterole in user.roles:
                await user.remove_roles(muterole)
                await ctx.send(f"Unmuted {user.mention} ({time} minutes passed)")

    @commands.command(aliases=["Unmute"])
    @commands.has_permissions(administrator=True)
    async def unmute(self, ctx, mention=None):
        role_id = database.get_attr("data", [str(ctx.guild.id), "roles", "muterole"], 0)
        muterole = ctx.message.guild.get_role(role_id)
        if muterole is None:
            await ctx.send(f"Muterole for this server is invalid or not set, please use -rolesetup muterole")
            return

        if mention is None:
            await ctx.send("Give me a user to unmute!")

        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        await user.remove_roles(muterole)
        await ctx.send(f"Unmuted {user.mention}")


def setup(client):
    client.add_cog(Moderation(client))
