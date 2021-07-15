import discord
import logging
from logging.handlers import RotatingFileHandler
from discord.ext.commands import Bot, has_permissions, MissingPermissions
from discord.utils import get
from pytz import timezone
from datetime import datetime, timedelta
from tzlocal import get_localzone
import dateparser
import os
import traceback
from typing import Union
from subprocess import Popen, PIPE
import re
import random

import asyncio

from hockey import hockey
from background.gamechannel import GameChannel
from background.armchairgm import ArmchairGM
from background.four_twenty import FourTwenty
from util import create_embed, settings

PREFIX = '$'
intents = discord.Intents().default()
intents.members = True
bot = Bot(command_prefix=PREFIX, intents=intents)
bot.remove_command('help')
with open('token', 'w') as f:
	TOKEN = f.read().strip()
cfg = settings.Settings()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
# add a rotating handler
handler = RotatingFileHandler('/root/discord/hn/log/main.log', maxBytes=5*1024*1024,
                              backupCount=5)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

@bot.event
async def on_ready():
	log.info(f'Bot connected as {bot.user}')
	await bot.change_presence(activity = discord.Game('Hockey'))
	gc = GameChannel(bot, cfg)
	log.info("Starting GameChannel...")
	bot.loop.create_task(gc.run())

	agm = ArmchairGM(bot)
	log.info("Starting ArmchairGM...")
	bot.loop.create_task(agm.run())

	ft = FourTwenty(bot)
	log.info("Starting FourTwenty...")
	bot.loop.create_task(ft.run())

@bot.event
async def on_member_join(member):
	if 'h0nde' in member.name.lower() or 'honde' in member.name.lower():
		await member.ban(reason='h0nde')

"""@bot.event
async def on_message(message):
	if message.content == 'test':
		await message.channel.send('Testing 1 2 3!')"""

@bot.command(name="help", description="Returns all commands available")
async def help(ctx):
	commands = bot.commands
	admin_role = get(bot.guilds[0].roles, id=348226061076791298)
	admin = admin_role in ctx.author.roles

	file, embed = await create_embed.help(admin, commands, PREFIX)

	await ctx.send(embed=embed, file=file)

@bot.command(name='open', description='Opens game chat. ADMIN ONLY!')
@has_permissions(administrator=True)
async def open(ctx):
	log.info(f"{ctx.author.name} opened game channels")
	worker_tasks = []

	for channel_id in await cfg.get_channels('GameChannels'):
		for role in await cfg.get_roles('GameChannels'):
			wt = asyncio.ensure_future(open_channel(channel_id, int(role), ctx))
			worker_tasks.append(wt)

	results = await asyncio.gather(*worker_tasks)

async def open_channel(channel_id, role, ctx):
	log.info(f'Opening {channel_id} for {role}')
	channel = bot.get_channel(int(channel_id))
	role = get(ctx.guild.roles, id=role)
	await channel.set_permissions(role, read_messages=True,
													  send_messages=None)
	await channel.send('Game chat is open!')

@open.error
async def open_error(ctx, error):
	log.info(f"{ctx.author.name} tried to open game channels")

@bot.command(name='close', description='Closes game chat. ADMIN ONLY!')
@has_permissions(administrator=True)
async def close(ctx):
	log.info(f"{ctx.author.name} closed game channels")
	worker_tasks = []

	for channel_id in await cfg.get_channels('GameChannels'):
		for role in await cfg.get_roles('GameChannels'):
			wt = asyncio.ensure_future(close_channel(channel_id, int(role), ctx))
			worker_tasks.append(wt)

	results = await asyncio.gather(*worker_tasks)

async def close_channel(channel_id, role, ctx):
	log.info(f'Closing {channel_id}')
	channel = bot.get_channel(int(channel_id))
	role = get(ctx.guild.roles, id=role)
	await channel.set_permissions(role, read_messages=True,
													  send_messages=False)
	await channel.send('Game chat is closed!')

@close.error
async def close_error(ctx, error):
	log.info(f"{ctx.author.name} tried to close game channels")

@bot.command(name='game', description='Gets game for a specific date. Defaults to today.')
async def game(ctx, *date):
	log.info(f"Getting game for {str(date)}...")
	if date:
		date = ' '.join(date)
		try:
			date = datetime.strftime(dateparser.parse(date), "%Y-%m-%d")
		except:
			await ctx.send("Unrecognized date format")
			return
	else:
		date = None

	is_game, game_info = await hockey.get_game(None, date)
	log.info(game_info)

	if is_game:
		"""utctz = timezone('UTC')
		esttz = timezone('US/Eastern')
		time = game_info['gameDate']
		utc = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ")
		utc2 = utctz.localize(utc)
		est = utc2.astimezone(esttz)

		if est > esttz.localize(datetime.now()):
			played_tense = "We're playing"
		else:
			played_tense = "We played"

		time = datetime.strftime(est,  "%I:%M %p on %B %d, %Y")
		if game_info['teams']['away']['team']['id'] == 1:
			game_msg = f"at the {game_info['teams']['home']['team']['name']}"
		else:
			game_msg = f"against the {game_info['teams']['away']['team']['name']}"
		await ctx.send(f"Yes! {played_tense} {game_msg} @{time}")"""
		try:
			file, embed = await create_embed.create_game(game_info['gamePk'], f"{PREFIX}game")
			await ctx.send(file=file, embed=embed)
		except Exception as e:
			log.exception("Error with creating game")
			await ctx.send("Oops, something went wrong.")
	else:
		try:
			file, embed = await create_embed.no_game(date, f"{PREFIX}game")
			await ctx.send(file=file, embed=embed)
		except Exception as e:
			log.exception("Error with creating no_game")
			await ctx.send("Oops, something went wrong.")

@bot.command(name='nextgame', description='Gets the next upcoming game.')
async def nextgame(ctx):
	is_game, game_info = await hockey.next_game()
	log.info(game_info)

	if is_game:
		"""utctz = timezone('UTC')
		time = game_info['gameDate']
		utc = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ")
		utc2 = utctz.localize(utc)
		est = utc2.astimezone(timezone('US/Eastern'))
		time = datetime.strftime(est,  "%I:%M %p on %b %d %Y")
		if game_info['teams']['away']['team']['id'] == 1:
			game_msg = f"at the {game_info['teams']['home']['team']['name']}"
		else:
			game_msg = f"against the {game_info['teams']['away']['team']['name']}"

		await ctx.send(f"We're playing {game_msg} @{time} next!")"""

		try:
			file, embed = await create_embed.create_game(game_info['gamePk'], f"{PREFIX}nextgame")
			await ctx.send(file=file, embed=embed)
		except Exception as e:
			log.exception("Error with creating game")
			await ctx.send("Oops, something went wrong.")
	else:
		await ctx.send(':(')

@bot.command(name='gamechatrole', description='Set or remove role(s) for game chat. ADMIN ONLY!')
@has_permissions(administrator=True)
async def gamechatrole(ctx, action, *roles: discord.Role):
	log.info(f"{ctx.author.name} is {action} roles: {str(roles)}")
	roles_existing = await cfg.get_roles('GameChannels')
	if action == 'add':
		try:
			if roles_existing is None:
				await cfg.set_roles('GameChannels', [r.id for r in roles])
			else:
				add_roles = list(roles)
				for erole in roles_existing:
					if erole in roles:
						add_roles.remove(erole)
				roles = roles_existing + add_roles
				await cfg.set_roles('GameChannels', [r.id if isinstance(r, discord.Role) else r for r in roles])
			await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with updating game channel roles")
			await ctx.message.add_reaction('❌')
	elif action == 'remove':
		try:
			if roles_existing is None:
				await ctx.message.add_reaction('❌')
				await ctx.send("Oops, no roles are set. Try `add`ing some.")
			else:
				rem_roles = list(roles)
				tmp = list(roles_existing)
				for erole in roles_existing:
					if erole in rem_roles:
						tmp.remove(erole)

				if len(tmp) > 0:
					roles = tmp
					await cfg.set_roles('GameChannels', [r.id if isinstance(r, discord.Role) else r for r in roles])
				else:
					roles = None
					await cfg.set_roles('GameChannels', roles)
				await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with deleting game channel roles")
			await ctx.message.add_reaction('❌')
	else:
		await ctx.send(f"Invalid argument. `{PREFIX}gamechatrole <add/remove> <@roles>`")

@gamechatrole.error
async def gamechatrole_error(ctx, error):
	log.info(f"{ctx.author.name} tried to gamechatrole")
	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}gamechatrole <add/remove> <@roles>`")

@bot.command(name='autorole', description='Set Stream Watcher role for user(s) for game chat. ADMIN ONLY!')
@has_permissions(administrator=True)
async def autorole(ctx, action, *members: discord.Member):
	log.info(f"{ctx.author.name} is {action} users from autorole")
	users_existing = await cfg.get_auto_role_users('GameChannels')
	if action == 'add':
		try:
			if users_existing is None:
				await cfg.set_auto_role_users('GameChannels', [m.id for m in members])
			else:
				add_users = list(members)
				for euser in users_existing:
					if euser in members:
						add_users.remove(euser)
				users = users_existing + add_users
				await cfg.set_auto_role_users('GameChannels', [m.id if isinstance(m, discord.Member) else m for m in users])
			await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with updating auto role users")
			await ctx.message.add_reaction('❌')
	elif action == 'remove':
		try:
			if users_existing is None:
				await ctx.message.add_reaction('❌')
				await ctx.send("Oops, no users are set. Try `add`ing some.")
			else:
				rem_users = list(members)
				tmp = list(users_existing)
				for euser in users_existing:
					if euser in rem_users:
						tmp.remove(euser)

				if len(tmp) > 0:
					users = tmp
					await cfg.set_auto_role_users('GameChannels', [m.id if isinstance(m, discord.Member) else m for m in users])
				else:
					users = None
					await cfg.set_users('GameChannels', users)
				await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with deleting auto role users")
			await ctx.message.add_reaction('❌')
	else:
		await ctx.send(f"Invalid argument. `{PREFIX}autorole <add/remove> <@users>`")

@autorole.error
async def autorole_error(ctx, error):
	log.exception(f"{ctx.author.name} tried to autorole")
	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}autorole <add/remove> <@users>`")

@bot.command(name='gamechannel', description='Set or remove channel(s) for game chat. ADMIN ONLY!')
@has_permissions(administrator=True)
async def gamechannel(ctx, action, *channels: discord.TextChannel):
	log.info(f"{ctx.author.name} is {action} game channels: {str(channels)}")
	channels_existing = await cfg.get_channels('GameChannels')
	if action == 'add':
		try:
			if channels_existing is None:
				await cfg.set_channels('GameChannels', [c.id for c in channels])
			else:
				add_channels = list(channels)
				for echannel in channels_existing:
					if echannel in channels:
						add_channels.remove(echannel)
				channels = channels_existing + add_channels
				await cfg.set_channels('GameChannels', [c.id if isinstance(c, discord.Channel) else c for c in roles])
			await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with updating game channels")
			await ctx.message.add_reaction('❌')
	elif action == 'remove':
		try:
			if channels_existing is None:
				await ctx.message.add_reaction('❌')
				await ctx.send("Oops, no channels are set. Try `add`ing some.")
			else:
				rem_channels = list(channels)
				tmp = list(channels_existing)
				for echannel in channels_existing:
					if echannel in rem_channels:
						tmp.remove(echannel)

				if len(tmp) > 0:
					channels = tmp
					await cfg.set_channels('GameChannels', [c.id if isinstance(c, discord.Channel) else c for c in roles])
				else:
					channels = None
					await cfg.set_channels('GameChannels', channels)
				await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with deleting game channels")
			await ctx.message.add_reaction('❌')
	else:
		await ctx.send(f"Invalid argument. `{PREFIX}gamechannel <add/remove> <#channels>`")

@gamechannel.error
async def gamechannel_error(ctx, error):
	log.info(f"{ctx.author.name} tried to setgamechannel")
	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}gamechannel <add/remove> <#channels>`")

@bot.command(name='highlightchannel', description='Set or remove channel(s) for highlights. ADMIN ONLY!')
@has_permissions(administrator=True)
async def highlightchannel(ctx, action, *channels: discord.TextChannel):
	log.info(f"{ctx.author.name} is {action} highlight channels: {str(channels)}")
	channels_existing = await cfg.get_channels('HighlightChannels')
	if action == 'add':
		try:
			if channels_existing is None:
				await cfg.set_channels('HighlightChannels', [c.id for c in channels])
			else:
				add_channels = list(channels)
				for echannel in channels_existing:
					if echannel in channels:
						add_channels.remove(echannel)
				channels = channels_existing + add_channels
				await cfg.set_channels('HighlightChannels', [c.id if isinstance(c, discord.Channel) else c for c in roles])
			await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with updating highlight channels")
			await ctx.message.add_reaction('❌')
	elif action == 'remove':
		try:
			if channels_existing is None:
				await ctx.message.add_reaction('❌')
				await ctx.send("Oops, no channels are set. Try `add`ing some.")
			else:
				rem_channels = list(channels)
				tmp = list(channels_existing)
				for echannel in channels_existing:
					if echannel in rem_channels:
						tmp.remove(echannel)

				if len(tmp) > 0:
					channels = tmp
					await cfg.set_channels('HighlightChannels', [c.id if isinstance(c, discord.Channel) else c for c in roles])
				else:
					channels = None
					await cfg.set_channels('HighlightChannels', channels)
				await ctx.message.add_reaction('✅')
		except Exception as e:
			log.exception("Error with deleting highlight channels")
			await ctx.message.add_reaction('❌')
	else:
		await ctx.send(f"Invalid argument. `{PREFIX}highlightchannel <add/remove> <#channels>`")

@highlightchannel.error
async def highlightchannel_error(ctx, error):
	log.info(f"{ctx.author.name} tried to sethighlightchannel")
	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}highlightchannel <add/remove> <#channels>`")

@bot.command(name='setrole', description='Set role for users. ADMIN ONLY!')
@has_permissions(administrator=True)
async def setrole(ctx, role: discord.Role, *users: discord.Member):
	for user in users:
		log.info(f"{ctx.author.name} is giving {role.name} to {user.name}")

		if role not in user.roles:
			await user.add_roles(role)
			if role.name == 'Stream Watcher':
				await user.edit(nick='🌐 ' + user.display_name + ' 🌐')
			await ctx.send(f"{user.name} has been given a role called: {role.name}")

@setrole.error
async def setrole_error(ctx, error):
	log.info(f"{ctx.author.name} tried to giving a role")
	log.error(traceback.format_exc())

	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}setrole @role @user(s)`")

@bot.command(name='unsetrole', description='Usnet role for users. ADMIN ONLY!')
@has_permissions(administrator=True)
async def unsetrole(ctx, role: discord.Role, *users: Union[discord.Member, str]):
	if isinstance(users[0], str):
		if users[0].lower() == 'all':
			users = role.members
		else:
			raise

	for user in users:
		log.info(f"{ctx.author.name} is removing {role.name} from {user.name}")

		await user.remove_roles(role)
		if role.name == 'Stream Watcher':
			if '🌐' in user.display_name:
				name = re.sub('🌐', '', user.display_name)
			await user.edit(nick=name)
		await ctx.send(f"{user.name} has been stripped of a role called: {role.name}")

@unsetrole.error
async def unsetrole_error(ctx, error):
	log.info(f"{ctx.author.name} tried to giving a role")
	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}unsetrole @role @user(s)/all`")
	log.exception("error ")

@bot.command(name='getconfig', description='Gets bot\'s settings. ADMIN ONLY!')
@has_permissions(administrator=True)
async def getconfig(ctx):
	log.info(f"{ctx.author.name} is getting config")
	names = ["Game Channels", "Game Channels Role", "Highlight Channels", "Auto Stream Watcher"]

	gc = ', '.join(f"<#{ch}>" for ch in await cfg.get_channels('GameChannels'))
	gr = ', '.join(f"<@&{r}>" for r in await cfg.get_roles('GameChannels'))
	hc = ', '.join(f"<#{ch}>" for ch in await cfg.get_channels('HighlightChannels'))
	ar = ', '.join(f"<@{r}>" for r in await cfg.get_auto_role_users('GameChannels'))

	values = [gc, gr, hc, ar]

	embed = await create_embed.create('Config', "Bot's settings", names, values, f"{PREFIX}getconfig")

	await ctx.send(embed=embed)

@bot.command(name='friedman', description='Generate an Elliotte Friedmanesque team name')
async def friedman(ctx, *, team):
	if len(team) < 4:
		await ctx.send("Team must be AT LEAST **4** characters!")
		return

	friedman = ''
	charNo = -1
	if ' ' in team:
		team = re.sub(' ', '', team)
		stop = 4
	else:
		stop = 3

	while len(friedman) < stop:
		charNo = random.randint(charNo+1, len(team)+(len(friedman)-(stop+1)))
		friedman += team[charNo]

	if team.lower().endswith('s'):
		friedman = friedman + 'S'

	await ctx.send(friedman.upper())

@getconfig.error
async def getconfig_error(ctx, error):
	log.info(f"{ctx.author.name} tried to get config")

@bot.command(name='restart', description='Restarts the bot. ADMIN ONLY!')
@has_permissions(administrator=True)
async def restart(ctx):
	log.info(f"{ctx.author.name} is restarting the bot")

	await ctx.send("BRB...")
	os.system("service devsbot restart")

@restart.error
async def restart_error(ctx, error):
	log.info(f"{ctx.author.name} tried to restart the bot")

@bot.command(name='csay', description='Send a message to a specific channel as the bot. ADMIN ONLY!')
@has_permissions(administrator=True)
async def csay(ctx, channel: discord.TextChannel, *, msg):
	log.info(f"{ctx.author.name} is sending a message to {channel.name}")

	await channel.send(msg)

@csay.error
async def csay_error(ctx, error):
	log.info(f"{ctx.author.name} tried to send a message to {channel.name}")

	if not isinstance(error, MissingPermissions):
		await ctx.send(f"Invalid argument. `{PREFIX}csay #channel <message>`")

@bot.command(name='kill', description='Kills the bot. ADMIN ONLY!')
@has_permissions(administrator=True)
async def kill(ctx):
	log.info(f"{ctx.author.name} is killing the bot")

	await ctx.send("Goodbye cruel world!")
	os.system("service devsbot stop")

@kill.error
async def kill_error(ctx, error):
	log.info(f"{ctx.author.name} tried to kill the bot")

lockfile = "/root/discord/hn/background/highlights.lock"
if os.path.exists(lockfile):
	os.remove(lockfile)
bot.run(TOKEN)