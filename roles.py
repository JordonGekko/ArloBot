import discord
from discord.ext import commands
from datetime import datetime
from dateutil.relativedelta import relativedelta
import spreadsheet
import asyncio
import main


database = main.database


class Roles:

    def __init__(self, client):
        self.client = client
        self.running = False
        self.subscription_times = {"1month": relativedelta(days=+30),
                                   "3months": relativedelta(days=+90),
                                   "6months": relativedelta(days=+180),
                                   "lifetime": None}

    async def on_ready(self):
        if not self.running:
            await self.refresh_loop()

    async def refresh_loop(self):
        self.running = True
        while True:
            try:
                await self.spreadsheet_update()
                await self.update_all_roles()
            except Exception as e:
                print(f"Ignored exception in refresh loop:\n{e}")

            sleep_for = 3600 - datetime.utcnow().minute * 60 - datetime.utcnow().second + 60
            print("sleeping for", sleep_for)
            await asyncio.sleep(sleep_for)

    async def update_from_sql(self):
        for guild in database.get_attr("data", [], []):
            guild = self.client.get_guild(int(guild))
            if guild is not None:
                rows = spreadsheet.get_all_rows()
                for row in rows:
                    trid = row['transaction_id']
                    if trid in database.get_attr("data", [str(guild.id), "transactions"], []):
                        print(f"transaction id {trid} already processed, skipping")
                        continue

                    userid = row['discord_id']
                    member = guild.get_member(userid)
                    if member is None:
                        print(f"user {userid} not found")
                        continue

                    response = await self.add_sub_to_user(guild, member, relativedelta(days=+row['duration']),
                                                          datetime.fromtimestamp(row['purchase_date']))
                    database.append_attr("data", [str(guild.id), "transactions"], trid)
                    if response is True:
                        print(f"added sub to {member} transaction id {trid}")
                    elif response is False:
                        print(f"Skipped transaction id {trid}, already expired")

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

    async def add_sub_to_user(self, guild, member, timedelta, time_added=datetime.utcnow()):
        oldtime = time_added.timestamp()

        # check if subscription during another
        if database.get_attr("data", [str(guild.id), "users", str(member.id)]) is not None:
            endtime = database.get_attr("data", [str(guild.id), "users", str(member.id), "ends_on"])
            if endtime is not None:
                if datetime.fromtimestamp(endtime) > datetime.utcnow():
                    oldtime = endtime

        # check for lifetime
        if timedelta is not None:
            end = (datetime.fromtimestamp(oldtime) + timedelta).timestamp()
            if datetime.fromtimestamp(end) < datetime.utcnow():
                return False
        else:
            end = None

        new_user = {
            "username": member.name + "#" + member.discriminator,
            "date_added": oldtime,
            "ends_on": end
        }

        # add role and database entry
        role = self.get_saved_role(guild)
        if role not in member.roles:
            await member.add_roles(role)
            channel = guild.get_channel(database.get_attr("data", [str(guild.id), "channel"]))
            if channel is not None:
                await self.announce(channel, member, timedelta.days)
        database.set_attr("data", [str(guild.id), "users", str(member.id)], new_user)
        return True

    async def remove_sub_from_user(self, guild, member):
        role = self.get_saved_role(guild)
        await member.remove_roles(role)
        database.set_attr("data", [str(guild.id), "users", str(member.id)], None)

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

    async def announce(self, channel, user, duration, date="date_here"):
        content = discord.Embed()
        content.title = "New subscriber"
        content.set_thumbnail(url=user.avatar_url)
        content.description = f"**{user.name}#{user.discriminator}** just subscribed for **{duration} days**!" \
                              f"\non **{date}**"
        await channel.send(embed=content)

    async def spreadsheet_update(self):
        for guild in database.get_attr("data", [], []):
            sheet_id = database.get_attr("data", [str(guild), "sheet_id"])
            if sheet_id is None:
                continue
            spreadsheet.read_sheet(sheet_id)
            await self.update_from_sql()

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
            await ctx.send(f"Mute role successfully set to **{role.name}**")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def forcerefresh(self, ctx):
        amount = await self.update_all_roles()
        await ctx.send(f"All roles updated. {amount} subscriptions expired")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def sheetid(self, ctx, sheet_id):
        database.set_attr("data", [str(ctx.guild.id), "sheet_id"], sheet_id)
        await ctx.send(f"Google sheet id set to {sheet_id}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, mention):
        channel = await commands.TextChannelConverter().convert(ctx, mention)
        if channel is None:
            await ctx.send("Invalid channel")
            return

        database.set_attr("data", [str(ctx.guild.id), "channel"], channel.id)
        await ctx.send(f"Announcement channel set to {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def readsheet(self, ctx):
        await self.spreadsheet_update()
        await ctx.send("done")

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
                ends_on = datetime.fromtimestamp(end_ts).strftime('%d/%m/%Y %H:%M:%S')
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
        if mention is None:
            await ctx.send("Give me user to check")
            return

        try:
            user = await commands.MemberConverter().convert(ctx, mention)
        except discord.ext.commands.errors.BadArgument:
            await ctx.send("There was an error getting the user.")
            return

        remains = self.get_remaining_time(ctx.guild, user)
        if remains is not None:
            end_ts = database.get_attr("data", [str(ctx.guild.id), "users", str(user.id), "ends_on"])
            if end_ts is not None:
                ends_on = datetime.fromtimestamp(end_ts).strftime('%d/%m/%Y %H:%M:%S')
            else:
                ends_on = "Never"
            await ctx.send(f"**{user.name}#{user.discriminator}** has a subscription with **{remains}** remaining."
                           f"\nEnds on: {ends_on}")
        else:
            await ctx.send(f"No subscription found for **{user.name}#{user.discriminator}**")


def setup(client):
    client.add_cog(Roles(client))
