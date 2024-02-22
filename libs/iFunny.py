import requests
import webbrowser
import json
import asyncio
import aiohttp
import traceback
from termcolor import colored
from datetime import datetime
import time
import textwrap
import sys
import sqlite3
import io
import fleep
from urllib.request import urlopen
from . import ws_client

host = "http://api.ifunny.mobi"

def get_or_gen_basic():

	with open(".//libs/Auth.json", "r") as file:
		Auth = json.load(file)
		if Auth.get("basic"):
			return Auth["basic"]


	from secrets import token_hex
	from hashlib import sha1
	from base64 import b64encode
	client_id = "JuiUH&3822"
	client_secret = "HuUIC(ZQ918lkl*7"
	device_id = token_hex(32)
	hashed = sha1(f"{device_id}:{client_id}:{client_secret}".encode('utf-8')).hexdigest()
	basic = b64encode(bytes(f"{f'{device_id}_{client_id}'}:{hashed}", 'utf-8')).decode()
	return basic


def cprint(*args, end_each=" ", end_all=""):
	dt = str(datetime.fromtimestamp(int(time.time())))
	print(colored(dt, "white"), end=end_each)
	for i in args:
		print(colored(str(i[0]), i[1].lower()), end=end_each)
	print(end_all)
	
	
async def get_request(url):
	async with aiohttp.ClientSession() as session:
		async with session.get(url) as r: 
			return await r.json()
			
			
async def post_request(url, data=None):
	async with aiohttp.ClientSession() as session:
		async with session.post(url, data=data) as r: 
			return await r.json()
			
basic = get_or_gen_basic()

class LoginError(Exception): pass
			
class Parser:

	version = "7b2274797065223a2022626f74227d"

	@staticmethod
	async def chat_list(bot, ctx, frame):

		bot.chats = [Chat(i, bot) for i in frame["chat_list"]]

	@staticmethod
	async def invitations(bot, ctx, frame):
		
		for i in frame["invitations"]:
			ctx.chat = Chat(i["chat"], bot)
			ctx.chat.inviter = User(i["inviter"], bot)
			await bot.accept_invite(ctx)
			cprint(("Joined chat", "magenta"), (i["chat"]["id"], "yellow"))				
				
	@staticmethod
	async def error(bot, ctx, frame):
		
		if frame["error"] == "message_rate_limit":
			bot.ratelimit()
			if package := bot.unconfirmed_queue.get(frame["response_to"]):
				await asyncio.sleep(0.5)
				await bot.message_queue.put(package)
			
			
	@staticmethod
	async def affirmation(bot, ctx, frame):
		
		if bot.unconfirmed_queue.get(frame["response_to"]):
			del bot.unconfirmed_queue[frame["response_to"]]
				
				
	@staticmethod
	async def chat_event(bot, ctx, frame):
		
		if function := bot.events.get(frame["chat_event"]):
			ctx.chat = Chat(frame["chat"], bot)
			
			if frame["user"]:
				if frame["user"]["id"] == bot.user_id: return
				ctx.user = User(frame["user"], bot)
			
			ctx.chat.yield_ratelimit = True
			bot.run_callback(function, ctx)
				
				
	@staticmethod
	async def member_list(bot, ctx, frame):
		
		if chat_id := bot.member_request_ids.get(frame["response_to"]):
			if q := bot.member_list_queues.get(chat_id):
				await q.put(frame["member_list"])
		
		
	@staticmethod
	async def message(bot, ctx, frame):
		
		user_id = frame["user"]["id"]
		
		if user_id == bot.user_id: return
		if frame["user"].get("is_bot"): return
		
		ctx.chat = Chat(frame["chat"], bot)
		ctx.message = Message(frame["message"], bot)
		ctx.author = User(frame["user"], bot)
		ctx.message.author = ctx.author
		ctx.chat.message = ctx.message
		ctx.message.chat = ctx.chat
		ctx.chat.author = ctx.author
		ctx.author.is_developer = ctx.author.id == bot.developer
		
		frame["message"]["text"] = frame["message"]["text"].strip()
				
		if frame["message"]["text"].startswith(bot.prefix):

			if command_items := frame["message"]["text"].strip(bot.prefix).strip().split():
				base_name = command_items[0].lower()
				
				if function := bot.commands.get(base_name):
					await bot.run_command(function, ctx)
				
		else:
			await bot.siphon_input(bot.on_message, ctx)
				
				
	@staticmethod
	async def file(bot, ctx, frame):
		
		user_id = frame["user"]["id"]
		
		if user_id == bot.user_id: return
		if frame["user"].get("is_bot"): return
		if user_id in bot.blacklist() and user_id != bot.developer: return

		if bot.on_file:
			
			ctx.chat = Chat(frame["chat"], bot)
			ctx.message = File(frame["file"], bot)
			ctx.author = User(frame["user"], bot)
			ctx.message.author = ctx.author
			ctx.chat.message = ctx.message
			ctx.message.chat = ctx.chat
			ctx.author.is_developer = ctx.author.id == bot.developer
			await bot.siphon_input(bot.on_file, ctx)

async def user_by_nick(nick: str, bot=None):
	userheader = {
    'Host': 'api.ifunny.mobi',
    'Accept': 'video/mp4, image/jpeg',
    'Applicationstate': '1',
    'Accept-Encoding': 'gzip, deflate',
    'Ifunny-Project-Id': 'iFunny',
    'User-Agent': 'iFunny/8.1.1(22616) iphone/14.0.1 (Apple; iPhone8,4)',
    'Accept-Language': 'en-US;q=1',
    'Authorization': 'Basic ' + basic,}

	data = requests.get(host+'/v4/users/by_nick/'+nick, headers=userheader).json()

	if data["status"] == 200:
		return User(data["data"], bot)
		
		
		
async def user_by_id(user_id: str, bot=None):

	userheader = {
    'Host': 'api.ifunny.mobi',
    'Accept': 'video/mp4, image/jpeg',
    'Applicationstate': '1',
    'Accept-Encoding': 'gzip, deflate',
    'Ifunny-Project-Id': 'iFunny',
    'User-Agent': 'iFunny/8.1.1(22616) iphone/14.0.1 (Apple; iPhone8,4)',
    'Accept-Language': 'en-US;q=1',
    'Authorization': 'Basic ' + basic,}

	data = requests.get(host+"/v4/users/"+user_id,headers=userheader)
	data = data.json()
	if data["status"] == 200:
	
		return User(data["data"], bot)
	
async def get_profile(bearer):	
	
	headers = {"Authorization":"Bearer " + bearer,'Ifunny-Project-Id': 'iFunny','User-Agent': 'iFunny/8.1.1(22616) iphone/14.0.1 (Apple; iPhone8,4)'}
	req = requests.get(host + "/v4/account",headers = headers).json()
	if req["status"] == 200:
		return True
	return False

class CTX:
	
	chat = None
	message = None
	author = None
	user = None
	inviter = None
	
	def __init__(self, bot=None):
		self.bot = bot
		
	async def user(self, nick_or_id):
		return await(user(nick_or_id, self.bot))
		
	async def user_by_nick(self, nick: str):
		return user_by_nick(nick, self.bot)
		
	async def user_by_id(self, user_id: str):
		return user_by_id(user_id, self.bot)
		
		
class CTXtype:
	
	def __init__(self, data, bot):
		self.bot = bot
		for k, v in data.items():
		  setattr(self, k, v)
		
			
class User(CTXtype):
	
	def __init__(self, data, bot):
		super().__init__(data, bot)
		
		
		self.chat_id = bot.user_id+"_"+self.id
		self.meme_experience = data.get("meme_experience")
		self.privacy = data.get("messaging_privacy_status")
		self.bans = data.get("bans")
		self.bio = data.get("about")
		self.cover = data.get("cover_url")
		self.num = data.get("num")
		self.name = self.nick
		self.role = data.get("role")
		self.status = data.get("last_seen_at")
		self.is_bot = data.get("is_bot")
		self.pfp = data.get("photo")
		self.verified = data.get("is_verified")
		self.banned = data.get("is_banned")
		self.deleted = data.get("is_deleted")
		self.og_nick = data.get("original_nick")
		self.blacklisted = self.id in bot.blacklist()
		self.developer = self.id == bot.developer
		
	def __eq__(self, other):
		return self.id == other.id
		
	def __ne__(self, other):
		return self.id != other.id
		
	async def send(self, message):
		await self.bot.send_message(self.chat_id, message)
		
	async def upload(self, data, messageid=None):
		await self.bot.upload(self.chat_id, data=data, messageid=messageid)
		
		
async def user(nick_or_id: str, bot=None):
	
	nick_or_id = nick_or_id.lower()
	
	if len(nick_or_id) == 24 and nick_or_id[0].isdigit() and sum([1 for i in nick_or_id if ord(i) >= 96]): #most likely to be an id
		if test_user := await user_by_id(nick_or_id, bot):
			return test_user
	
	return await user_by_nick(nick_or_id, bot)
	

class Message(CTXtype):
	
	def __init__(self, data, bot):
		super().__init__(data, bot)
		self.author = None
		self.chat = None
		self.text = self.text.strip()
		self.payload = data.get("payload")
		self.args_list = self.text.split(" ")[int(bool(self.text.startswith(bot.prefix))):]
		self.args = " ".join(self.args_list)
		self.ts = self.pub_at
		self.ping = int(time.time()*1000)-self.ts
		
	def __eq__(self, other):
		return self.text == other.text
		
	def __ne__(self, other):
		return self.text != other.text
		
		
class File(CTXtype):
	
	def __init__(self, data, bot):
		super().__init__(data, bot)
		for k, v in data["file"].items():
			setattr(self, k, v)
		self.author = None
		self.chat = None
		self.ts = self.pub_at
		self.ping = int(time.time()*1000)-self.ts
		
	def __eq__(self, other):
		return self.hash == other.hash
		
	def __ne__(self, other):
		return self.hash != other.hash
		
		
class Chat(CTXtype):
	
	def __init__(self, data, bot):
		super().__init__(data, bot)
		self.bot_role = data.get("role") #0 is owner, 1 is operator (public chats), 2 is member
		self.type = data.get("type") #1 is dm, 2 is private, 3 is public
		self.type_name = data.get("type_name")
		self.description = data.get("description")
		self.cover = data.get("cover")
		self.name = data.get("name")
		self.title = data.get("title")
		self.total_members = data.get("members_total")
		self.unread = data.get("messages_unread")
		self.last_msg = data.get("last_msg")
		
		self.author = None
		self.message = None
		self.inviter = None
		self.yield_ratelimit = False
		
	def __eq__(self, other):
		return self.id == other.id
		
	def __ne__(self, other):
		return self.id != other.id
		
	async def send(self, message):
		if self.yield_ratelimit and self.bot.ratelimited: return
		author_name = None
		if self.author and self.type != 1: author_name = self.author.nick
		await self.bot.send_message(self.id, message, author_name)
		
	async def upload(self, data, messageid=None):
		await self.bot.upload(chat_id=self.id, data=data, messageid=messageid)
		
	async def members(self):
		return await self.bot.get_members(self.id)
	
	async def set_pfp(self, url):
		return await self.bot.set_chat_pfp(self.id, url)
	
	async def set_name(self, name):
		return await self.bot.set_chat_title(self.id, name)
	
	async def mute(self):
		return await self.bot.mute_chat(self.id)
	
	async def unmute(self):
		return await self.bot.unmute_chat(self.id)
		
	async def has_member(self, user):
		for i in await self.members():
			if user == i: return True
		return False
		
	async def invite(self, user):
		await self.bot.invite(self.id, user.id)

	async def kick(self, user):
		await self.bot.kick(self.id, user.id)
		
	async def input(self, type=Message, timeout=None):
		return await self.bot.input(self.id, type, timeout)


class Bot:
	
	def __init__(self, email: str, password: str, region: str, prefix: str, developer: str):
	
		assert(prefix), "Prefix string cannot be empty"
	
		self.email = email
		self.password = password
		self.region = region
		self.prefix = prefix
		self.bearer = ""
		self.user_id = ""

		with open("./libs/Auth.json", "r") as Auth:
			Auth = json.load(Auth)
			if Auth.get("basic"):
				self.basic = Auth.get("basic")
				self.bearer = Auth.get("bearer")
				self.user_id = Auth.get("user_id")
			else:
				self.basic = get_or_gen_basic()

		regions = {"United States": "ifunny", "Brazil": "ifunny_brazil"}
		
		assert(region in regions), "Invalid region"
		
		self.ws_region = regions[region]
		
		cprint(("Starting bot...", "magenta"))
		
		self.nick = ""
		self.commands = {}
		self.events = {}
		self.cooldowns = {}
		self.timekeeping = {}
		self.developer_commands = []
		self.developer = developer
		self.help_categories = {}
		self.command_help_messages = {}
		self.member_list_queues = {}
		self.member_request_ids = {}
		self.chat_request_ids = {}
		self.chat_list_queues = {}
		self.chats = []
		self.ratelimited = False
		self.open = True
		self.on_join = self.on_message = self.on_file = None
		self.prev_chat_id = self.prev_message = self.prev_nick = None
		self.unconfirmed_queue = {}
		self.siphons = {}
		self.generate_help_command()
		self._blacklist = set()
		self.load_blacklist()
		self.login()


	def login(self):

		paramz = {'grant_type':'password',
			  'username': self.email,
			  'password': self.password }
		
		header = {'Host': 'api.ifunny.mobi','Applicationstate': '1','Accept': 'video/mp4, image/jpeg','Content-Type': 'application/x-www-form-urlencoded','Authorization': 'Basic '+self.basic,'Content-Length':'77','Ifunny-Project-Id': 'iFunny','User-Agent': 'iFunny/8.1.1(22616) iphone/14.0.1 (Apple; iPhone8,4)','Accept-Language': 'en-US;q=1','Accept-Encoding': 'gzip, deflate'}
		userheader = {'Host': 'api.ifunny.mobi','Accept': 'video/mp4, image/jpeg','Applicationstate': '1','Accept-Encoding': 'gzip, deflate','Ifunny-Project-Id': 'iFunny','User-Agent': 'iFunny/7.14.2(22213) iphone/14.0.1 (Apple; iPhone8,4)','Accept-Language': 'en-US;q=1','Authorization': 'Basic '+self.basic,}
		index = 0

		while True:

			if self.bearer:
				self.buff = ws_client.Buffer(self.bearer, self.user_id, self.ws_region, self.parse)
				return	
			
			login = requests.post(host + "/v4/oauth2/token", headers=header, data=paramz).json()
			
			if "error" in login:

				if login["error"] == "captcha_required":
					cprint(("Captcha required, Please solve the captcha, then type \"Done\": ","red"))
					time.sleep(3)
					captcha_url = login["data"]["captcha_url"]
					webbrowser.open_new(captcha_url)
					input()					
					cprint(("Logging in...","green"))
					continue

				if login["error"] == "unsupported_grant_type":
					time.sleep(10)
					continue

				if login["error"] == "too_many_user_auths":
					raise LoginError("auth rate succeeded, try again later")
				
				if login["error"] == "forbidden":
					index += 1
					if index > 1:
						raise LoginError("Your email or password is incorrect! Please check your credentials and try again.")
					requests.get(host+"/v4/counters", headers=userheader)
					cprint(("Priming your basic auth token...", "green"))
					time.sleep(10)
					continue

				if login["error"] == "invalid_grant":
					raise LoginError("Your email or password is incorrect! Please check your credentials and try again.")

			break        

		self.bearer = login["access_token"]
		acctheader = {"Authorization":"Bearer " + self.bearer,'Ifunny-Project-Id': 'iFunny','User-Agent': 'iFunny/8.1.1(22616) iphone/14.0.1 (Apple; iPhone8,4)'}
		Account = requests.get(host + "/v4/account", headers = acctheader).json()
		self.user_id = Account["data"]["id"]

		with open("./libs/Auth.json", "r") as File:
			Auth = json.load(File)
			Auth["bearer"] = self.bearer
			Auth["user_id"] = self.user_id
			Auth["basic"] = self.basic
			with open("./libs/Auth.json", "w") as F:
				json.dump(Auth, F, indent = 1)

		self.buff = ws_client.Buffer(self.bearer, self.user_id, self.ws_region, self.parse)
		
		
	def command(self, *args, **kwargs):
		def container(function):
		
			name = kwargs.get("name")
			if not name: name  = function.__name__
			name = name.lower()
			self.commands[name] = function
			
			if not kwargs.get("hide_help"):
				help_category = kwargs.get("help_category")
				if help_category: help_category = str(help_category).lower()
				
				if not self.help_categories.get(help_category):
					self.help_categories[help_category] = []
				
				self.help_categories[help_category].append(name)
				help_message = function.__doc__
				if kwargs.get("help_message"): help_message = kwargs.get("help_message")
				self.command_help_messages[function] = help_message
				
			if aliases := kwargs.get("aliases"):
				for alias in aliases:
					self.commands[alias] = function
					
			if cooldown := kwargs.get("cooldown"):
				self.cooldowns[function] = cooldown
				
			if kwargs.get("developer"):
				self.developer_commands.append(function)
			
			def decorator(*dargs, **dkwargs):
				return function(*dargs, **dkwargs)
			
			return decorator
		return container
		
		
	def event(self, *args, **kwargs):
		def container(function):
		
			name = function.__name__
			valid_types = ("user_join", "user_leave", "user_kick", "channel_change", "on_join", "on_message", "on_file")
			assert (name in valid_types), "Function name for an event must be in "+", ".join(valid_types)
			
			if name in valid_types[4:]: setattr(self, name, function)
			else: self.events[name] = function

			def decorator(*dargs, **dkwargs):
				function(*dargs, **dkwargs)

			return decorator
		return container
		

	def run(self):
		
		try:
			asyncio.run(self.run_tasks())
		
		except KeyboardInterrupt:
			print()
			cprint(("Bot has shut down", "red"))
		
		except:
			cprint(("Bot has shut down due to error", "red"))
			traceback.print_exc()
		
		finally:
			self.blacklist_db_con.commit()
			self.blacklist_db_con.close()
			sys.exit(0)
			
		
	def disconnect(self):
		cprint(("Shutting down bot...", "red"))
		self.buff.disconnect()
		self.open = False
		

	async def run_tasks(self):
	
		self.message_queue = asyncio.Queue()
		await asyncio.gather(
			asyncio.create_task(self.message_queuer()),
			asyncio.create_task(self.buff.run()))
				
				
	async def siphon_input(self, callback, ctx):
		
		if ctx.chat.id in self.siphons:
			for t, q in self.siphons[ctx.chat.id].items():
				if t == any or type(ctx.message) == t:
					await q.put(ctx.message)
		
		if callback:
			self.run_callback(callback, ctx)
			
			
	async def input(self, chat_id, type=Message, timeout=None):
		
		if not self.siphons.get(chat_id):
			self.siphons[chat_id] = {}
			
		if not self.siphons[chat_id].get(type):
			self.siphons[chat_id].update({type: asyncio.Queue()})
		
		try:
			message = await asyncio.wait_for(self.siphons[chat_id][type].get(), timeout)
		
		except:
			message = None
			
		del self.siphons[chat_id][type]
		if not self.siphons[chat_id]:
			del self.siphons[chat_id]
			
		return message
		
		
	def blacklist(self, user=None):
		
		if not user:
			return list(self._blacklist)
		
		if isinstance(user, User):
			user = user.id
		
		if user == self.developer:
			return False
			
		self._blacklist.add(user)
		self.blacklist_db_con.execute("INSERT INTO users VALUES (?)", (user,))
		self.blacklist_db_con.commit()
		return True
		
		
	def whitelist(self, user):
		
		if isinstance(user, User):
			user = user.id
			
		if user not in self._blacklist:
			return False
			
		self._blacklist.remove(user)
		self.blacklist_db_con.execute("DELETE FROM users WHERE id = ?", (user,))
		self.blacklist_db_con.commit()
		return True

	def load_blacklist(self):
		
		self.blacklist_db_con = sqlite3.connect("libs/data/blacklist.db")
		self.blacklist_db_cur = self.blacklist_db_con.cursor()
		self.blacklist_db_cur.execute("CREATE TABLE IF NOT EXISTS users (id TEXT, unique(id))")
		self.blacklist_db_con.commit()
		self._blacklist = set([i[0] for i in self.blacklist_db_cur.execute("SELECT * FROM users")])
			

	async def message_queuer(self):
	
		while self.open:
		
			if self.ratelimited:
				await asyncio.sleep(60)
				self.unratelimit()
				self.unconfirmed_queue = {}
				
				queue_dict = {}
				
				while not self.message_queue.empty():
					chat_id, message, nick = await self.message_queue.get()
					message = str(message)
					if not queue_dict.get(chat_id): queue_dict[chat_id] = []
					#if nick: message = nick+": "+message
					queue_dict[chat_id].append(message)
					
				for k, v in queue_dict.items():
					message = "\n\n".join(v)
					await self.message_queue.put((k, message, None))
					
				continue
					
			chat_id, message, nick = await self.message_queue.get()
			
			if self.ratelimited:
				await self.message_queue.put((chat_id, message, nick))
				continue
			
			try:
				payload = json.loads(bytes.fromhex(Parser.version).decode("utf-8"))
			
			except:
				return self.disconnect()
				
			request_id = int(time.time()*1000000)
			package = (chat_id, message, nick)
			self.unconfirmed_queue[request_id] = package
			
			try:
				await self.buff.send_ifunny_ws(await self.buff.form_ifunny_frame(
					{"type": "message", "message": message,
					"chat_id": chat_id,
					"request_id": request_id,
					"payload": payload}))
				
			except Exception as ex:
				cprint(("Failed to send message because:", "magenta"), (str(ex), "red"))
				
			
			
	async def send_message(self, chat_id, message, nick=None):
	
		chunks = textwrap.wrap(str(message), 500, break_long_words=True, replace_whitespace=False)
		
		for message in chunks:
			await self.message_queue.put((chat_id, message, nick))



	async def accept_invite(self, ctx):
		await self.buff.send_ifunny_ws(await self.buff.form_ifunny_frame({"type": "accept_invitation", "chat_id": ctx.chat.id}))
		if self.on_join:
			await asyncio.sleep(0.1)
			self.run_callback(self.on_join, ctx)

	
	async def reject_invite(self, ctx):
		await self.buff.send_ifunny_ws(await self.buff.form_ifunny_frame({"type": "decline_invitation", "chat_id": ctx.chat.id}))
		cprint(("Rejected invite from blacklist:","red"),(f"{ctx.chat.title}","cyan"))


	async def get_chat(self,chat_id):
		request_id = int(time.time()*1000)
		self.member_request_ids[request_id] = chat_id
		
		self.chat_list_queues[chat_id] = asyncio.Queue()
		await self.buff.send_ifunny_ws(await self.buff.form_ifunny_frame({"type": "get_chat","chat_id": chat_id, "request_id": request_id}))
		try:
			chat_info = await asyncio.wait_for(self.chat_list_queues[chat_id].get(), 3)
		except asyncio.TimeoutError:
			chat_info = []

		del self.chat_list_queues[chat_id]
		return chat_info
			
	async def get_members(self, chat_id):
		request_id = int(time.time()*1000)
		self.member_request_ids[request_id] = chat_id
		self.member_list_queues[chat_id] = asyncio.Queue()
		await self.buff.send_ifunny_ws(await self.buff.form_ifunny_frame({"type": "list_members", "chat_id": chat_id, "request_id": request_id}))
		
		try:
			member_list = await asyncio.wait_for(self.member_list_queues[chat_id].get(), 3)
		except asyncio.TimeoutError:
			member_list = []
			
		del self.member_list_queues[chat_id]
		member_list = [User(i, self) for i in member_list]
		return member_list
		
		
	async def invite(self, chat_id, user_id):
		await self.buff.send_ifunny_ws(await self.buff.form_ifunny_frame({"type": "send_invitation", "user_id": user_id, "chat_id": chat_id}))


	async def kick(self, chat_id, user_id):
		await self.buff.send_ifunny_ws(json.dumps([48,self.buff.ifunny_ws_counter,{},"co.fun.chat.kick_member",[],{"chat_name":f"{chat_id}","user_id":f"{user_id}"}]))

		
	async def set_chat_pfp(self, chat_id, url):
		await self.buff.send_ifunny_ws(json.dumps([48,self.buff.ifunny_ws_counter,{},"co.fun.chat.edit_chat",[],{"unset":[],"set":{"cover":f"{url}"},"chat_name":f"{chat_id}"}]))


	async def set_chat_title(self, chat_id, title):
		await self.buff.send_ifunny_ws(json.dumps([48,self.buff.ifunny_ws_counter,{},"co.fun.chat.edit_chat",[],{"unset":[],"set":{"title":f"{title}"},"chat_name":f"{chat_id}"}]))


	async def mute_chat(self, chat_id):
		await self.buff.send_ifunny_ws(json.dumps([48,self.buff.ifunny_ws_counter,{},"co.fun.chat.freeze_chat",[],{"chat_name":f"{chat_id}"}]))


	async def unmute_chat(self, chat_id):
		await self.buff.send_ifunny_ws(json.dumps([48,self.buff.ifunny_ws_counter,{},"co.fun.chat.unfreeze_chat",[],{"chat_name":f"{chat_id}"}]))

	
	async def upload(self, chat_id, data, messageid=None):

		if isinstance(data, str):
			if "https://" in data:
				data = urlopen(data)

		data = io.BytesIO(data.read())

		await self.buff.send_ifunny_ws(json.dumps([48, self.buff.ifunny_ws_counter, {}, "co.fun.chat.message.create_empty", [], {"chat_name": f"{chat_id}"}]))
		await asyncio.sleep(.3)
		message_id = ws_client.message_ids[0]
		await self.buff.send_ifunny_ws(json.dumps([48, self.buff.ifunny_ws_counter, {}, "co.fun.chat.get_chat", [], {"chat_name": f"{chat_id}"}]))

		headers = {
			"Host": "api.ifunny.mobi",
			"Accept": "video/mp4, image/jpeg",
			"Accept-Encoding": "gzip, deflate",
			"Connection": "close",
			"ApplicationState": "1",
			"Authorization": "Bearer " + self.bearer,
			"iFunny-Project-Id": "iFunny",
			"User-Agent": "iFunny/8.1.1(22616) iphone/14.0.1 (Apple; iPhone8,4)",
			"Accept-Language": "en-US;q=1, zh-Hans-US;q=0.9"
			}

		mime = fleep.get(data.getvalue()).mime

		if mime:
			datatype = mime[0]
			if datatype.startswith("image/"):
				upload_type = "pic"
				if datatype.endswith("/gif"):
					upload_type = "gif"
			elif datatype.startswith("video/"):
				upload_type = "video_clip"
		
		if upload_type == "video_clip":
			file_type = "video"
		else:
			file_type = "image"
		re = requests.post(url='https://api.ifunny.mobi/v4/content', data={'message_id':message_id, 'type':upload_type, 'tags':[], 'description':'', 'visibility':'chats'}, headers=headers, files={file_type: ("image.tmp", data.getvalue(), mime[0])}).json()
		
			
		
	async def parse(self, frame):
	
		ctx = CTX(self)
	
		if hasattr(Parser, frame["type"]):
			await getattr(Parser, frame["type"])(self, ctx, frame)
						
						
	def ratelimit(self):
		if not self.ratelimited:
			self.ratelimited = True
			cprint(("Ratelimited", "red"))
		
		
	def unratelimit(self):
		if self.ratelimited:
			self.ratelimited = False
			cprint(("Ratelimit unlocked", "magenta"))
		
		
	async def run_command(self, function, ctx):
	
		if function in self.developer_commands and not ctx.author.is_developer:
			return
	
		ratelimit = self.cooldowns.get(function)
		now = time.time()
		
		if not ctx.author.is_developer:
			if ratelimit:
				user_timekeeping = self.timekeeping.get(ctx.author.id)
				if user_timekeeping:
					ratelimit_expires_at = user_timekeeping.get(function)
					if ratelimit_expires_at:
						if now < ratelimit_expires_at:
							remaining_time = int(ratelimit_expires_at-now)
							remaining_time_str = seconds_to_str(remaining_time)
							return await ctx.chat.send(f"You must wait {remaining_time_str} before you can use this command again")
						else:
							del self.timekeeping[ctx.message.author.id][function]
		
		if not self.timekeeping.get(ctx.author.id):
			self.timekeeping[ctx.author.id] = {}
			
		if self.cooldowns.get(function):
			self.timekeeping[ctx.author.id][function] = now+self.cooldowns[function]
		
		cprint((ctx.author.id, "yellow"), (ctx.author.nick, "green"), (ctx.message.text.strip(self.prefix), "cyan"))
		self.run_callback(function, ctx, *ctx.message.args_list)
		
		
	def run_callback(self, function, *args):
		asyncio.get_event_loop().create_task(function(*args))


	def generate_help_command(self):
	
		@self.command(hide_help=True)
		async def help(ctx, *args):
			
			self = ctx.bot
		
			if args:
				
				if command_list := self.help_categories.get(args[0].lower()):
					response = "List of commands"
					response += f"\n▼{args[0].title()}\n\n"
					response += "\n".join([self.prefix+i for i in command_list
						if (not self.commands[i] in self.developer_commands or
						(ctx.author.is_developer and self.commands[i] in self.developer_commands))])
					response += f"\n\nUse \"{ctx.bot.prefix}help (command name)\" for detailed usage help."
			
				elif function := self.commands.get(args[0]):
					function_help = self.command_help_messages[function]
					if not function_help: function_help = "No help message for this command has been written"
					response = f"{self.prefix}{function.__name__}\n\n{function_help}"
					
				else:
					response = f"A category or command with that name does not exist. Check \"{self.prefix}help\" for the full list of commands."
				
			else:
				response = "List of command categories:\n\n"
				response += "\n".join(["‣"+i for i in self.help_categories.keys() if i])
				
				if None in self.help_categories:
					response += "\n\nFor support and feedback:\n"
					response += "\n".join([self.prefix+i for i in self.help_categories[None]
						if (not self.commands[i] in self.developer_commands or
						(ctx.author.is_developer and self.commands[i] in self.developer_commands))])
					
				response += f"\n\nUse \"{self.prefix}help (category)\" for detailed usage help."
				
			await ctx.chat.send(response)
		


def seconds_to_str(t):
	
	y, r = divmod(t, 31557600)
	month, r = divmod(r, 2629800)
	d, r = divmod(r, 86400)
	h, r = divmod(r, 3600)
	m, s = divmod(r, 60)
	durations = [[int(y),"year"],[int(month),"month"],[int(d),"day"],[int(h),"hour"],[int(m),"minute"],[int(s),"second"]]
	durations = [i for i in durations if i[0]]
	s_durations = []

	for count, i in enumerate(durations):
		if i[0] > 1:
			durations[count][1] += "s"
			
	durations = [str(i[0])+" "+i[1] for i in durations]
	total = ", ".join(durations)

	if t > 0:
		return total
	
	return "1 second"

