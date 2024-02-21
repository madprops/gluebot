import requests, websockets, asyncio, json, re, traceback, subprocess, os, aiohttp, sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
username = os.environ.get("GLUEBOT_USERNAME")
password = os.environ.get("GLUEBOT_PASSWORD")

def get_time():
	return datetime.now().timestamp()

def remove_file(path):
	try:
		path.unlink()
	except Exception as e:
		print(f"(Remove) Error: {e}")
		traceback.print_exc()

def get_extension(path):
	return Path(path).suffix.lower().lstrip(".")

headers = {
	"User-Agent": "renabot",
	"Origin": "https://deek.chat",
	"DNT": "1",
}

url = "https://deek.chat"
ws_url = "wss://deek.chat/ws"
prefix = ","
token = None
session = None
delay = 3

gifmaker = "/usr/bin/gifmaker"
gm_common = "--width 350 --nogrow --output /tmp/gifmaker"

cmd_date = get_time()

def update_time():
	global cmd_date
	cmd_date = get_time()

def blocked():
	return (get_time() - cmd_date) < delay

def auth():
	global token, session, headers

	if not username or not password:
		print("Missing environment variables")
		exit(1)

	data = {"name": username, "password": password, "submit": "log+in"}
	res = requests.post(url + "/login/submit", headers=headers, data=data, allow_redirects=False)
	token = re.search("(?:api_token)=[^;]+", res.headers.get("Set-Cookie")).group(0)
	session = re.search("(?:session_id)=[^;]+", res.headers.get("Set-Cookie")).group(0)
	headers["Cookie"] = token + "; " + session

async def run():
	async with websockets.connect(ws_url, extra_headers=headers) as ws:
		try:
			while True:
				message = await ws.recv()
				await on_message(ws, message)
		except KeyboardInterrupt:
			exit(0)
		except websockets.exceptions.ConnectionClosedOK:
			print("WebSocket connection closed")
		except Exception as e:
			print("(WebSocket) Error:", e)
			traceback.print_exc()

async def on_message(ws, message):
	if blocked(): return

	try:
		data = json.loads(message)
	except:
		return

	if data["type"] == "message":
		if data["data"]["name"] == username:
			return

		text = data["data"]["text"].strip()

		if not text.startswith(prefix):
			return

		room_id = data["roomId"]
		words = text.lstrip(prefix).split(" ")
		cmd = words[0]
		args = words[1:]

		if cmd == "ping":
			update_time()
			await send_message(ws, "Pong!", room_id)

		elif cmd == "help":
			update_time()
			await send_message(ws, f"Commands: describe | wins | numbers | date | bird", room_id)

		elif cmd == "describe":
			if len(args) >= 1:
				update_time()
				await gif_describe(args[0], room_id)

		elif cmd == "wins" or cmd == "win":
			if len(args) >= 1:
				update_time()
				await gif_wins(args[0], room_id)

		elif cmd == "numbers" or cmd == "number" or cmd == "nums" or cmd == "num":
			update_time()
			await gif_numbers(None, room_id)

		elif cmd == "date" or cmd == "data" or cmd == "time" or cmd == "datetime":
			update_time()
			await gif_date(None, room_id)

		elif cmd == "bird" or cmd == "birds" or cmd == "birb" or cmd == "birbs" or cmd == "brb":
			update_time()
			await gif_bird(None, room_id)

def get_input_path(name):
	return str(Path(HERE, name))

async def gif_describe(who, room_id):
	input_path = get_input_path("describe.jpg")

	command = [
		gifmaker,
		gm_common,
		f"--input '{input_path}'",
		f"--words '{who} is\\n[Random] [x5]'",
		"--filter anyhue2 --opacity 1 --fontsize 66 --delay 700",
		"--padding 50 --fontcolor light2 --bgcolor dark2",
	]

	await run_gifmaker(command, room_id)

async def gif_wins(who, room_id):
	input_path = get_input_path("wins.gif")

	command = [
		gifmaker,
		gm_common,
		f"--input '{input_path}'",
		f"--words '{who} wins a ; [repeat] ; [RANDOM] ; [repeat]' --bgcolor 0,0,0",
		"--bottom 20 --filter anyhue2 --framelist 11,11,33,33 --fontsize=42",
	]

	await run_gifmaker(command, room_id)

async def gif_numbers(who, room_id):
	input_path = get_input_path("numbers.png")

	command = [
		gifmaker,
		gm_common,
		f"--input '{input_path}'",
		"--top 20 --words '[number 0-999] [x3]' --fontcolor 0,0,0 --fontsize 66",
	]

	await run_gifmaker(command, room_id)

async def gif_date(who, room_id):
	input_path = get_input_path("time.jpg")

	command = [
		gifmaker,
		gm_common,
		f"--input '{input_path}'",
		"--words 'Date: [date %A %d] ; [repeat] ; Time: [date %I:%M %p] ; [repeat]'",
		"--filter anyhue2 --bottom 20 --bgcolor 0,0,0 --fontsize 80",
	]

	await run_gifmaker(command, room_id)

async def gif_bird(who, room_id):
	input_path = get_input_path("bird.png")

	command = [
		gifmaker,
		gm_common,
		f"--input '{input_path}'",
		"--words '[randomx]' --randomfile data/aves.txt --bgcolor 0,0,0",
		"--filter anyhue2 --frames 3 --fontsize 42 --fillwords",
	]

	await run_gifmaker(command, room_id)

async def run_gifmaker(command, room_id):
	process = await asyncio.create_subprocess_shell(
		" ".join(command),
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		shell=True,
	)

	stdout, stderr = await process.communicate()

	if process.returncode != 0:
		print(f"(Process) Error: {stderr.decode()}")
		return

	await upload(Path(stdout.decode().strip()), room_id)

async def upload(path, room_id):
	if (not path.exists()) or (not path.is_file()):
		return

	cookies = {
		"session_id": session.split("=")[1],
		"api_token": token.split("=")[1],
	}

	ext = get_extension(path)
	url = "https://deek.chat/message/send/" + str(room_id)
	data = aiohttp.FormData()
	data.add_field(name="files[]", value=open(path, "rb"), \
	filename=path.name, content_type=f"image/{ext}")

	try:
		async with aiohttp.ClientSession(cookies=cookies) as sess:
			async with sess.post(url, data=data, headers={}) as response:
				await response.text()
	except Exception as e:
		print(f"(Upload) Error: {e}")
		traceback.print_exc()

	remove_file(path)

async def send_message(ws, text, room_id):
	await ws.send(json.dumps({"type": "message", "data": text, "roomId": room_id}))

while True:
	try:
		auth()
		print("Authenticated")
		asyncio.run(run())
	except KeyboardInterrupt:
		break
	except Exception as e:
		print("(Main) Error:", e)
		traceback.print_exc()