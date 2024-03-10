from ast import excepthandler
from asyncio.events import get_child_watcher
from asyncio.windows_events import INFINITE
from datetime import datetime
from urllib.request import urlopen
import random
import time

from libs import iFunny
from libs.iFunny import User
from libs import ws_client
from libs.ws_client import Buffer
from termcolor import colored


email = "" # The iFunny account your bot will run on. 
password = "" # Input your account's password
region = "United States"  # or "Brazil" for Brazilian chat servers.
prefix = "" # Choose a symbol your bot will respond to. Examples: / . , ! $ > 
developer = "" # Your iFunny user ID. Best place to get this would be to use an existing bot's id command.

bot = iFunny.Bot(email, password, region, prefix, developer)
basicauth = bot.basic
bearer = bot.bearer

def cprint(*args, end_each=" ", end_all=""):
	dt = str(datetime.fromtimestamp(int(time.time())))
	print(colored(dt, "white"), end=end_each)
	for i in args:
		print(colored(str(i[0]), i[1].lower()), end=end_each)
	print(end_all)


# Commands
	

@bot.command(help_category="tools",help_message="Search for a user")
async def user(ctx,*args):
	chat = ctx.chat
	user = await ctx.user(args[0])
	if not user:
		return await chat.send("That user doesn't exist.")
	return await chat.send(f"https://ifunny.co/user/{user.nick.lower()}")

					
@bot.command(help_category="tools",help_message="Sends the account name of a user ID")
async def whois(ctx,*args):
	chat = ctx.chat	
	user = await ctx.user(args[0])	
	if not user:
		return await chat.send("This is not a user ID")
	return await chat.send(f"Username: {user.original_nick}\n\nhttps://ifunny.co/user/{user.original_nick}")


@bot.command(help_category="tools",help_message="Invites a user to the chat!",aliases=["summon","inv","add"])
async def invite(ctx,username=None,*args):
	chat = ctx.chat
	
	if chat.type == 1:
		return await chat.send("You cant invite users to a dm.")
	
	if not username:
		return
	
	user = await ctx.user(username)
	
	if not user:
		return await chat.send("That user doesnt exist")
	
	if await chat.has_member(user):
		return await chat.send("That user is already in the chat")
	
	return await chat.invite(user)

	

@bot.command(help_category="tools",help_message="Find the current online members of a chat!",aliases=["online"])
async def expose(ctx,*args):
	chat = ctx.chat
	members = await chat.members()
	msg = "Users online:\n\n"

	for member in members:
		if member.status != 0:
			continue
		
		msg += f"{member.nick}\n"

	return await chat.send(msg)



@bot.command(hide_help=True)
async def chatid(ctx, *args):
	chat = ctx.chat
	await chat.send(ctx.chat.id)


@bot.command(hide_help=True, developer=True, aliases = ["bl"])
async def blacklist(ctx, *args):
	chat = ctx.chat

	if args:
		user = await ctx.user(args[0])
		if not user:
			return await chat.send("Input a valid username")		
		ctx.bot.blacklist(user)
		return await chat.send(f"{user.nick} has been blacklisted")
	
	return await chat.send(f"There are {len(ctx.bot.blacklist())} Blacklisted Users")


@bot.command(hide_help=True, developer=True, aliases = ["wl"])
async def whitelist(ctx, *args):
	chat = ctx.chat
	if args:
		user = await ctx.user(args[0])
		ctx.bot.whitelist(user)
		return await chat.send(f"{user.nick} has been whitelisted")


@bot.command(help_category="tools",help_message="Display a user's profile picture",cooldown=60)
async def pfp(ctx,*args):
	chat = ctx.chat
	
	if args:
		user = await ctx.user(args[0])
	else:
		user = await ctx.user(ctx.message.author.nick)

	if not user:
		return await chat.send("That user doesnt exist")
	
	if not user.pfp:
		return await chat.send("That user has no profile picture!")
	
	url = urlopen(user.pfp.get("url"))
	try:
		await chat.upload(url)
	except Exception as e:
		return await chat.send(f"Error uploading image\n\n{e}")
	

@bot.command(help_category="tools",help_message="Sends the cover of the user you specify")
async def cover(ctx,*args):
	chat = ctx.chat

	if not args:
		user = await ctx.user(ctx.message.author.nick)
	else:
		user = await ctx.user(args[0])

	if not user:
		return await chat.send("That user doesnt exist.")
	
	cover = user.cover
	if not cover:
		return await chat.send("That user doesn't have a cover photo.")
	
	try:
		await chat.upload(cover)
	except Exception as e:
		return await chat.send(f"Error uploading image\n\n{e}")
	

@bot.command(help_category="tools",help_message="Displays the chat's pfp")
async def chatpfp(ctx,*args):
	chat = ctx.chat
	cover = ctx.chat.cover
	if not cover:
		return await chat.send("This chat doesnt have a cover!")
	cover = urlopen(cover)
	try:
		await chat.upload(cover)
	except Exception as e:
		return await chat.send(f"Error uploading image\n\n{e}")


@bot.command(help_category="general")
async def say(ctx, *args):
	"""I will repeat you"""

	chat = ctx.chat
	message = ctx.message
	text = ctx.message.args

	return await chat.send(text)
		

@bot.command(help_category="fun")
async def dice(ctx,amount = 6,*args):
	chat = ctx.chat

	if not int(amount):
		return

	if int(amount) <= 0:
		return await chat.send("How are you supposed to roll nothing?")

	return await chat.send(f"You rolled a {amount} sided die and it came up {random.randint(1,amount)}")


@bot.command(help_category="fun",help_message="tells you how something something is.")
async def how(ctx, *args):
	chat = ctx.chat
	if len(args) == 2:
		return await chat.send(f"{args[0]} is {random.randrange(0,100)}% {args[1]}")


@bot.command(hide_help=True)
async def ping(ctx,*args):
	ping = ctx.message.ping
	return await ctx.chat.send(f"Pong! {ping}ms")


# Events


# When a user is kicked
@bot.event()
async def user_kick(ctx):	
	cprint((f"{ctx.user.nick} was kicked from {ctx.chat.title}", "cyan"), (f"({ctx.chat.id})", "green"))


# When a user leaves
@bot.event()
async def user_leave(ctx):
	cprint((f"{ctx.user.nick} has left {ctx.chat.title} ", "cyan"), (f"({ctx.chat.id})", "green"))


# When a user joins
@bot.event()
async def user_join(ctx):
	cprint((f"{ctx.user.nick} has joined {ctx.chat.title} ", "cyan"), (f"({ctx.chat.id})", "green"))


# When a user sends an image, gif, or video attachment
@bot.event()
async def on_file(ctx):
	cprint((f"{ctx.author.nick} sent an attachment in {ctx.chat.title}", "cyan"), (f"({ctx.chat.id})", "green"))


# When a user sends a message
@bot.event()
async def on_message(ctx):
	chat = ctx.chat
	message = ctx.message.args.replace("\n"," ")
	author = ctx.message.author
	cprint((f"{chat.title}", "cyan"),(f"{chat.id}","green"),(f"{author.nick}", "magenta"),(f"{message}", "blue"))


# When the bot gets invited to / joins a chat
@bot.event()
async def on_join(ctx):
	chat = ctx.chat
	if chat.type == 1:
		return
	await chat.send(f"{ctx.chat.inviter.nick} invited me! \nSay {ctx.bot.prefix}help for info.")

# Start the bot
bot.run()
