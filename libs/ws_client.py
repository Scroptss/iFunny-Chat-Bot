import websockets
import time
import asyncio
import json
import traceback
from datetime import datetime
from termcolor import colored
from . import iFunny
import ssl

def now_ms():
	return int(time.time()*1000)
	
def cprint(*args, end_each=" ", end_all=""):
	dt = str(datetime.fromtimestamp(int(time.time())))
	print(colored(dt, "white"), end=end_each)
	for i in args:
		print(colored(str(i[0]), i[1].lower()), end=end_each)
	print(end_all)

def USER_EVENT(ws_buffer, data):

	try:
		chat = data.copy()
		message = data.get("last_msg")
		
		del chat["touch_dt"]
		del chat["name"]
		chat["id"] = data["name"]
		user = data.get("user")
		chat["type_name"] = {1:"dm", 2:"private_group", 3:"public_group"}.get(chat.get("type"))
		
		if chat.get("inviter"):
			del chat["inviter"]
			
		if chat.get("user"):
			del chat["user"]
			
		if not chat.get("description"):
			chat["description"] = ""
			
		if message:
		
			del chat["last_msg"]
						
			if message.get("user"):
				user = message.get("user")
				del message["user"]
				
		if user:
			user["is_bot"] = False
			
			if message.get("payload"):
				user["is_bot"] = message["payload"].get("type") == "bot"
				
	except:
		print(data)
		traceback.print_exc()
		
	return message, chat, user
				
def MESSAGE(ws_buffer, data):

	message, chat, user = USER_EVENT(ws_buffer, data)
	return {"type": "message", "message": message, "chat": chat, "user": user}
	
		
def FILE(ws_buffer, data):

	message, chat, user = USER_EVENT(ws_buffer, data)
	message["file"] = message["files"][0].copy()
	del message["files"]
	
	return {"type": "file", "file": message, "chat": chat, "user": user}
	
	
def EVENT(ws_buffer, data):

	message, chat, user = USER_EVENT(ws_buffer, data)
	#message type: 3: join, 4: leave, 5: channel change, 6: kicked
	frame = {"type": "chat_event", "chat_event": "", "text": message, "chat": chat, "user": user}
	
	if message["type"] == 3:
		frame["chat_event"] = "user_join"
		frame["text"] = user["nick"]+" was added by "+message["inviter"]["nick"]
		
	elif message["type"] == 4:
		frame["chat_event"] = "user_leave"
		frame["text"] = user["nick"]+" left"
	
	elif message["type"] == 5:
		frame["chat_event"] = "channel_change"
		frame["text"] = "Chat information was updated"
		
	elif message["type"] == 6:
		frame["chat_event"] = "user_kick"
		frame["text"] = user["nick"]+" was kicked"
		
	return frame
		
message_ids = []
chat_frames = []
chat_info = []

async def RESULT(ws_buffer, response_to, data):
	try:
		key_list = list(data.keys())
		first_item = key_list[0]

		if first_item == "message_id":
			if message_ids != []:
					message_ids.clear()
			message_ids.append(data["message_id"])
			if q := ws_buffer.request_id_queues.get(response_to):
				await q.put(data["message_id"])
			return {"type": "file_id", "file_id": data["message_id"], "response_to": response_to}

		elif first_item == "members":
			#role 0 is admin, role 2 is member
			return {"type": "member_list", "member_list": data["members"], "response_to": response_to}
			
		elif data.get("messages"):
			if chat_frames != []:
				chat_frames.clear()
			chat_frames.append(data["messages"])
			if request_data := ws_buffer.request_ids.get(response_to):
				chat_id, _ = request_data
				del ws_buffer.request_ids[response_to]
				return {"type": "message_list", "message_list": data["messages"],
					"prev_cursor": data.get("prev"), "next_cursor": data.get("next"),
					"response_to": response_to, "chat_id": chat_id}
		elif first_item == "chat":
			if chat_info != []:
				chat_info.clear()
			chat_info.append(data)
			return None
			
		elif "chats" in key_list:
			chats = parse_all_chats(ws_buffer, data["chats"])
			
			return {"type": "chat_list", "chat_list": chats, "response_to": response_to}
			
	except:
		traceback.print_exc()
		print(data)
		
		
def INVITATIONS(ws_buffer, chats):

	invite_list = []

	for c in chats:
	
		chat = c.copy()
		inviter = c["inviter"]
		del chat["touch_dt"]
		del chat["name"]
		chat["id"] = c["name"]
		
		if not chat.get("description"):
			chat["description"] = ""
			
		invite_list.append({"chat": chat, "inviter": inviter})
		
	return {"type": "invitations", "invitations": invite_list}
	
	
async def ERROR(ws_buffer, response_to, data):
	
	if len(data) > 1:
		return {"type": "error", "error": data[-1][0]}
	
	else:
		
		error = data[0].split(":")[-1].strip()
		
		if request_data := ws_buffer.request_ids.get(response_to):
			chat_id, client_frame_data = request_data
			del ws_buffer.request_ids[response_to]
		
		if "rate limit for sending new messages" in error: error = "message_rate_limit"
		
		if "NotFoundChatException" in error:
			other_user_id = chat_id.split("_")[1]
			error = await ws_buffer.get_or_create_chat(chat_id, ws_buffer.user_id, other_user_id)
			if not error:
				client_frame_data["request_id"] = now_ms()
				ifunny_frame = await ws_buffer.form_ifunny_frame(client_frame_data)
				del ws_buffer.request_ids[client_frame_data["request_id"]]
				try: await ws_buffer.send_ifunny_ws(ifunny_frame)
				except: pass
				return
		
		return {"type": "error", "error": error, "response_to": response_to}
	
	
def AFFIRMATION(ws_buffer, response_to):
	if ws_buffer.request_ids.get(response_to):
		del ws_buffer.request_ids[response_to]
	return {"type": "affirmation", "response_to": response_to}
	
	
def parse_all_chats(ws_buffer, chat_list):

	response_formats = {1:MESSAGE, 2:FILE}
	response_formats.update({i:EVENT for i in range(3,7)})
	frames = []
	
	for chat_data in chat_list:
	
		message_data = chat_data.get("last_msg")
		
		if not message_data:
			continue
		
		if parser := response_formats.get(message_data["type"]):
			client_frame = parser(ws_buffer, chat_data)
			frames.append(client_frame)
		
		else:
			print("PARSER NOT FOUND")
			print(chat_data)
			continue
	
			
	return frames
	

class Buffer:

	def __init__(self, bearer, user_id, region, callback):
		
		self.bearer = bearer
		self.user_id = user_id
		self.region = region
		self.callback = callback
		self.nick = ""
		self.open = True
		self.ifunny_ws = None
		self.ifunny_ws_counter = 6
		self.init_chat_list_received = False
		self.last_client_call = time.time()*1000
		self.disconnect_after = 600000 #ms = 10 minutes
		self.request_ids = {}
		self.chat_id_ws_counter = {}
		self.subscription_codes = {}
		self.num_failed_auths = 0
		
		self.ifunny_wss_url = "wss://chat.ifunny.co/chat"
		
		self.headers = {"Sec-WebSocket-Protocol": "wamp.json"}
		
		self.init_call = json.dumps([1,f"co.fun.chat.{region}",
						{"authmethods":["ticket"],"roles":
						{"caller":{},"publisher":{},"subscriber":{}}}])
	def bearer(self):
		bearer = self.bearer
		return bearer
		
	async def run(self):
	
		self.request_id_queues = {}
		await self.run_ifunny()
		
	def disconnect(self):
		self.open = False
				
			
	async def run_ifunny(self):

		while self.open:
		
			frames = await self.listen_ifunny()
			if not frames: continue

			for f in frames:
				if f:
					await self.callback(f)
					
			
	async def send_ifunny_ws(self, data):
		
		await self.ifunny_ws.send(data)
		self.ifunny_ws_counter += 1

			
			
	async def connect_ifunny(self):
		
		try:
			self.ifunny_ws = await websockets.connect(self.ifunny_wss_url,
				subprotocols=["wamp.json"],
				extra_headers=self.headers)

			await self.ifunny_ws.send(self.init_call)
			cprint(("Websocket established", "magenta"))
		except Exception as e:
			cprint(("Error establishing websocket", "red"),(f"{e}","cyan"))
		
		
	async def listen_ifunny(self):
		

		if self.ifunny_ws:
		
			try:
				ifunny_frame = await self.ifunny_ws.recv()
				ifunny_frame = json.loads(ifunny_frame)
				
			except json.decoder.JSONDecodeError:
				return None
				
			except:
				await asyncio.sleep(5)
				await self.connect_ifunny()
				return None
				
			frame = await self.form_client_frame(ifunny_frame)
			return frame
		
		else:
			await self.connect_ifunny()
			return None
			


	
	#will take an ifunny format frame and parse it into client frame
	async def form_client_frame(self, frame):
	
		frame_type_id = frame[0]
		response_to = frame[1]
		frame_id = frame[2]
		frame_data = frame[-1]
		frame_format = None
		client_frame = {}
		
		
		if frame_type_id in (3, 6): #authentication error/shutdown
			if self.num_failed_auths >= 5:
				await self.callback(
					{"type": "authentication_error", "error": "internal authentication failure",
					"reason": "You must login again"})
				return None
				
			self.num_failed_auths += 1
			await self.connect_ifunny()
			return None
		
		elif frame_type_id == 4: #send bearer to authenticate
			try:
				await asyncio.sleep(2)
				await iFunny.get_profile(self.bearer)
				await self.ifunny_ws.send(json.dumps([5,self.bearer,{}]))
			except:
				await self.connect_ifunny()
			return None
			
		elif frame_type_id == 2: #send this stuff to allow sending messages
			await self.ifunny_ws.send(json.dumps([32,1,{},f"co.fun.chat.user.{self.user_id}.chats"]))
			await self.ifunny_ws.send(json.dumps([32,2,{},f"co.fun.chat.user.{self.user_id}.invites"]))
			cprint(("Authenticated as", "magenta"), (self.user_id, "yellow"))
			cprint(("Bot is online", "magenta"),)
			return None
		
		elif frame_type_id == 36: #this is either a message or a list of chats (which contain a message)
			
			if frame_data["type"] == 100: #100 is a message
				frames = parse_all_chats(self, frame_data["chats"])
				
				if len(frames) > 1:
					return [{"type": "chat_list", "chat_list": frames, "response_to": response_to}]
				#if not self.init_chat_list_received:
					#self.init_chat_list_received = True
					#return None
				return frames
				
			elif frame_data["type"] == 300: #this is a list of invites
				if not frame_data["chats"]: return None
				client_frame = INVITATIONS(self, frame_data["chats"])
				
			else:
				return None
				
		elif frame_type_id in (50,): #response to asking for an empty message
			if not frame_data: return None
			client_frame = await RESULT(self, response_to, frame_data)
			
		elif frame_type_id in (8,): #error
			#print(frame)
			client_frame = await ERROR(self, frame_id, frame_data)
			
		elif frame_type_id in (17,): #affirmation
			client_frame = AFFIRMATION(self, response_to)
			
		elif frame_type_id == 33:
			self.subscription_codes[self.chat_id_ws_counter.get(response_to)] = frame_id
			
		else: #other bs don't care about. might implement reads later
			print(frame)
			return None
			
		return [client_frame]
		

	#takes a client frame and parses it into ifunny format frame to send to ifunny
	async def form_ifunny_frame(self, frame):
		
		frame_type = frame.get("type")
		chat_id = frame.get("chat_id")
		request_id = frame.get("request_id")
		message = frame.get("message")
		other_user_id = frame.get("user_id")
		next_cursor = frame.get("next_cursor")
		prev_cursor = frame.get("prev_cursor")
		payload = frame.get("payload", {})
		
		if frame_type == "message":
		
			payload["local_id"] = "RainOS v1.4"
					
			if not request_id:
				request_id = self.ifunny_ws_counter
				
			self.request_ids[request_id] = (chat_id, frame)
		
			return json.dumps(
				[16,request_id,
				{"acknowledge":1},
				f"co.fun.chat.chat.{chat_id}",[],
				{"payload":payload,
				"message_type":1,"type":200,"text":message}])
				
		elif frame_type == "file_id":
			
			return json.dumps(
				[48,request_id,{},
				"co.fun.chat.message.create_empty",[chat_id],{}])
				
		elif frame_type == "leave_chat":
		
			return json.dumps(
				[48,self.ifunny_ws_counter,{},
				"co.fun.chat.leave_chat",[chat_id],{}])
				
		elif frame_type == "accept_invitation":
		
			return json.dumps(
				[48,self.ifunny_ws_counter,{},
				"co.fun.chat.invite.accept",[],
				{"chat_name":chat_id}])
				
		elif frame_type == "decline_invitation":
		
			return json.dumps(
				[48,self.ifunny_ws_counter,{},
				"co.fun.chat.invite.decline",[],
				{"chat_name":chat_id}])
				
		elif frame_type == "send_invitation":
		
			return json.dumps(
				[48,self.ifunny_ws_counter,{},
				"co.fun.chat.invite.invite",[],
				{"users":[other_user_id],"chat_name":chat_id}])

		elif frame_type == "kick_user":
		
			return json.dumps(
				[48,self.ifunny_ws_counter,{},
				"co.fun.chat.kick_member",[],
				{"chat_name":chat_id,"user_id":other_user_id}])
				
		elif frame_type == "list_chats":
		
			return json.dumps(
				[48,request_id,{},f"co.fun.chat.list_chats",[50],{}])
				
		elif frame_type == "list_invitations":
		
			return json.dumps(
				[48,request_id,{},f"co.fun.chat.invite.list",[],{}])
				
		elif frame_type == "list_members":

			return json.dumps(
				[48,request_id,{},
				"co.fun.chat.list_members",[],
				{"chat_name":chat_id,"limit":1000,"next":None}])

		elif frame_type == "get_chat":
			return json.dumps([48,request_id,{},"co.fun.chat.get_chat",[],{"chat_name":chat_id}])

		elif frame_type == "list_messages":
		
			self.request_ids[request_id] = (chat_id, None)
			has_cursor = any((next_cursor, prev_cursor))
			message_limit = 250
			
			if not has_cursor:
				next_cursor = now_ms()

			if next_cursor:
				return json.dumps(
					[48,request_id,{},
					"co.fun.chat.list_messages",[],
					{"chat_name":chat_id,"limit":message_limit,"next":next_cursor}])
					
			elif prev_cursor:
				return json.dumps(
					[48,request_id,{},
					"co.fun.chat.list_messages",[],
					{"chat_name":chat_id,"limit":message_limit,"prev":prev_cursor}])
					
			else:
				return None
				
		elif frame_type == "start_reading":
			
			self.chat_id_ws_counter[self.ifunny_ws_counter] = chat_id
			return json.dumps([32,self.ifunny_ws_counter,{},f"co.fun.chat.chat.{chat_id}"])
			
		elif frame_type == "stop_reading":
			
			if subscription_code := self.subscription_codes.get(chat_id):
				return json.dumps([34,self.ifunny_ws_counter,subscription_code])
				del self.subscription_codes.get[chat_id]
				
		else:
			return None
			
			
	async def get_or_create_chat(self, chat_id, user_id, other_user_id):
		
		other_user_data = self.web_app.user(other_user_id)
		dms = other_user_data["messaging_privacy_status"]
		
		if dms == "closed":
			return "user_dm_closed"
		
		elif dms == "subscribers":
			if user_id not in await self.web_app.subscriptions(other_user_id):
				return "user_not_subscribed"
		
		try:
			await self.send_ifunny_ws(json.dumps([48,self.ifunny_ws_counter,{},
				"co.fun.chat.get_or_create_chat",
				[1,chat_id,None,None,None,[other_user_id]],{}]))
				
		except:
			pass
			
		
