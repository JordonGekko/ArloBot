import discord
from discord.ext import commands
from datetime import datetime
from dateutil.relativedelta import relativedelta
import asyncio
import main


database = main.database


class Roles:

    def __init__(self, client):
        self.client = client
        self.subscription_times = {"1month": relativedelta(days=+30),
                                   "3months": relativedelta(days=+90),
                                   "6months": relativedelta(days=+180),
                                   "lifetime": None}

    async def on_ready(self):
        await self.refresh_loop()

    async def refresh_loop(self):
        while True:
            try:
                await self.update_all_roles()
                sleep_for = 3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second + 60
                print("sleeping for", sleep_for)
                await asyncio.sleep(sleep_for)
            except Exception as e:
                print(f"Ignored exception in refresh loop:\n{e}")
                continue

    async def update_all_roles(self):
        to_remove = []
        for guild in database.get_attr("data", [], []):
            for userid in database.get_attr("data", [guild, "users"], []):
                # check if needs to expire
                userdata = database.get_attr("data", [guild, "users", userid])
                if userdata is None:
                    continue
                end = userdata['ends_on']
                if end is not None:
                    if datetime.fromtimestamp(end) < datetime.utcnow():
                        # expired
                        guild = self.client.get_guild(int(guild))
                        member = guild.get_member(int(userid))
                        if member is not None:
                            await self.remove_sub_from_user(guild, member)
                            to_remove.append(userid)
                            print(f"Automatically removed subscription from {member.name}#{member.discriminator}")

        return len(to_remove)

    def get_saved_role(self, guild):
        try:
            roleid = database.get_attr("data", [str(guild.id), "roles", "subrole"])
            role = guild.get_role(roleid)
            return role
        except KeyError:
            return None

    def add_sub_to_user(self, guild, user, timedelta, subscription_name):
        try:
            if database.get_attr("data", [str(guild.id), "users", str(user.id)]) is not None:
                oldtime = database.get_attr("data", [str(guild.id), "users", str(user.id), "ends_on"])
            else:
                oldtime = datetime.utcnow().timestamp()

            if timedelta is not None:
                end = (datetime.fromtimestamp(oldtime) + timedelta).timestamp()
            else:
                end = None

            new_user = {
                "tier": subscription_name,
                "date_added": datetime.utcnow().timestamp(),
                "ends_on": end
            }
            database.set_attr("data", [str(guild.id), "users", str(user.id)], new_user)
            return True
        except Exception as e:
            print(f"Ignoring exception in def add_sub_to_user({guild},  {user}, {timedelta})")
            print(e)
            return False

    async def remove_sub_from_user(self, guild, member):
        try:
            role = self.get_saved_role(guild)
            await member.remove_roles(role)
            database.set_attr("data", [str(guild.id), "users", str(member.id)], None)
        except Exception as e:
            print(f"Ignoring exception in def remove_sub_from_user({guild}, {member})")
            print(e)

    def get_remaining_time(self, guild, user):
        try:
            userdata = database.get_attr("data", [str(guild.id), "users", str(user.id)])
            # date_added = userdata['date_added']
            ends_on = userdata['ends_on']
            if ends_on is not None:
                remains_delta = (datetime.fromtimestamp(ends_on) - datetime.utcnow()).total_seconds()
                if datetime.fromtimestamp(ends_on) < datetime.utcnow():
                    return "EXPIRED"
                m, s = divmod(remains_delta, 60)
                h, m = divmod(m, 60)
                d, h = divmod(h, 24)
                if d >= 1:
                    return "%d days %d hours" % (d, h)
                elif h >= 1:
                    return "%d hours %d minutes" % (h, m)
                else:
                    return "%d minutes %d seconds" % (m, s)
            else:
                return "lifetime"
        except (KeyError, TypeError):
            return None

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def rolesetup(self, ctx, assigntype,  mention):
        try:
            role = await commands.RoleConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the role.")
            return

        if assigntype == "subrole":
            database.set_attr("data", [str(ctx.guild.id), "roles", "subrole"], role.id)
            await ctx.send(f"Subscription role successfully set to **{role.name}**")
        elif assigntype == "muterole":
            database.set_attr("data", [str(ctx.guild.id), "roles", "muterole"], role.id)
            await ctx.send(f"Mute role role successfully set to **{role.name}**")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def forcerefresh(self, ctx):
        amount = await self.update_all_roles()
        await ctx.send(f"All roles updated. {amount} subscriptions expired")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def subscription(self, ctx, mention=None, time=None):
        if mention is None or time is None:
            await ctx.send("Invalid syntax.\n**Usage:** `-subscription [user] [timeframe]`")
            return

        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        role = self.get_saved_role(ctx.guild)
        if role is None:
            await ctx.send("There was an error getting the role. Make sure to set it with `rolesetup`")
            return

        delta = self.subscription_times.get(time, False)
        if delta is False:
            timeframes = " | ".join(self.subscription_times.keys())
            await ctx.send(f"Invalid timeframe `{time}`\n**Valid timeframes:** `[{timeframes}]`")
            return

        # all error checks are done
        response = self.add_sub_to_user(ctx.guild, user, delta, time)
        if response is True:
            await user.add_roles(role)
            end_ts = database.get_attr("data", [str(ctx.guild.id), "users", str(user.id), "ends_on"])
            if end_ts is not None:
                ends_on = datetime.fromtimestamp(end_ts).strftime('%m-%d-%y %H:%M:%S')
            else:
                ends_on = "Never"
            await ctx.send(f"Added {time} subscription to **{user.name}#{user.discriminator}**"
                           f"\nSet on expire on {ends_on}")
        else:
            await ctx.send("There was an error adding a user to the database.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removesub(self, ctx, mention=None):
        if mention is None:
            await ctx.send("Invalid syntax.\n**Usage:** `-subscription [user] [timeframe]`")
            return

        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        role = self.get_saved_role(ctx.guild)
        if role is None:
            await ctx.send("There was an error getting the role. Make sure to set it with `rolesetup`")
            return

        await self.remove_sub_from_user(ctx.guild, user)
        await ctx.send(f"Removed all subscriptions from **{user.name}#{user.discriminator}**")

    @commands.command()
    async def check(self, ctx, mention=None):
        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        remains = self.get_remaining_time(ctx.guild, user)
        if remains is not None:
            end_ts = database.get_attr("data", [str(ctx.guild.id), "users", str(user.id), "ends_on"])
            if end_ts is not None:
                ends_on = datetime.fromtimestamp(end_ts).strftime('%m-%d-%y %H:%M:%S')
            else:
                ends_on = "Never"
            await ctx.send(f"**{user.name}#{user.discriminator}** has a subscription with **{remains}** remaining."
                           f"\nEnds on: {ends_on}")
        else:
            await ctx.send(f"No subscription found for **{user.name}#{user.discriminator}**")


def setup(client):
    client.add_cog(Roles(client))
