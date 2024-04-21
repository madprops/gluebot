import requests
import websockets
import asyncio
import json
import re
import httpx
import traceback
import os
import aiohttp
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
import sys
import tempfile

HERE = Path(__file__).parent
username = os.environ.get("GLUEBOT_USERNAME")
password = os.environ.get("GLUEBOT_PASSWORD")

headers = {
    "User-Agent": "gluebot",
    "Origin": "https://deek.chat",
    "DNT": "1",
}

url = "https://deek.chat"
ws_url = "wss://deek.chat/ws"
prefix = ","
token = None
session = None
delay = 3
last_file = None
last_file_ext = None

gifmaker_common = [
    "gifmaker",
    "--width", 350,
    "--output", "/tmp/gifmaker",
    "--nogrow",
]


def msg(message: str) -> None:
    print(message, file=sys.stderr)


def get_time():
    return datetime.now().timestamp()


def remove_file(path):
    try:
        path.unlink()
    except Exception as e:
        msg(f"(Remove) Error: {e}")
        traceback.print_exc()


def get_extension(path):
    return Path(path).suffix.lower().lstrip(".")


def clean_lines(s):
    cleaned = s
    cleaned = re.sub(r" *(\n+|\\n+) *", "\n", cleaned)
    cleaned = re.sub(r" +", " ", cleaned)
    return cleaned.strip()


def random_int(min_val, max_val):
    return random.randint(min_val, max_val)


def random_date():
    one_hundred = 36525
    current_date = datetime.now()
    end_date = current_date + timedelta(days=(one_hundred // 2))
    random_days = random.randint(0, (end_date - current_date).days)
    random_date = current_date + timedelta(days=random_days)
    return random_date.strftime("%d %b %Y")


def get_path(name):
    return str(Path(HERE, name))


def extract_range(string):
    pattern = r"(?:(?P<number1>-?\d+)(?:\s*(.+?)\s*(?P<number2>-?\d+))?)?"
    match = re.search(pattern, string)
    num1 = None
    num2 = None

    if match["number1"]:
        num1 = int(match["number1"])

    if match["number2"]:
        num2 = int(match["number2"])

    return [num1, num2]


def clean_list(lst):
    return list(filter(lambda x: x != "", lst))


def string_to_number(input_string):
    hash_value = hash(input_string)
    absolute_hash = abs(hash_value)
    scaled_number = absolute_hash % 1000
    return scaled_number


def clean_string(string):
    string = string.replace("&#34;", '"')
    string = string.replace("&#39;", "'")
    string = string.replace("&quot;", '"')
    string = string.replace("&apos;", "'")
    string = string.replace("&amp;", "&")
    string = string.replace("&lt;", "<")
    string = string.replace("&gt;", ">")
    return string


def escape_quotes(string):
    return string.replace('"', '\\"')


def remove_char(string, char):
    return string.replace(char, "")


def clean_gifmaker(arg):
    arg = clean_string(arg)
    arg = remove_char(arg, ";")
    return arg


def join_command(command):
    return " ".join(f'"{arg}"' for arg in command)


def gifmaker_command(args):
    command = gifmaker_common.copy()
    command.extend(args)
    return join_command(command)


cmd_date = get_time()
userlist = []


def update_time():
    global cmd_date
    cmd_date = get_time()


def blocked():
    return (get_time() - cmd_date) < delay


def auth():
    global token, session, headers

    if not username or not password:
        msg("Missing environment variables")
        exit(1)

    data = {"name": username, "password": password, "submit": "log+in"}
    res = requests.post(url + "/login/submit", headers=headers, data=data, allow_redirects=False)
    token = re.search("(?:api_token)=[^;]+", res.headers.get("Set-Cookie")).group(0)
    session = re.search("(?:session_id)=[^;]+", res.headers.get("Set-Cookie")).group(0)
    headers["Cookie"] = token + "; " + session


def update_userlist(message):
    global userlist
    message = json.loads(message)
    event = message.get("type")

    if event == "loadUsers":
        userlist = []

        for key in message["data"]:
            room_users = message["data"][key]

            for user in room_users:
                name = user.get("name")

                if name:
                    userlist.append(name)
    elif event == "enter":
        name = message["data"].get("name")

        if name and (name not in userlist):
            userlist.append(name)
    elif event == "exit":
        name = message["data"].get("name")

        if name and (name in userlist):
            userlist.remove(name)


async def run():
    async with websockets.connect(ws_url, extra_headers=headers) as ws:
        try:
            while True:
                message = await ws.recv()
                update_userlist(message)
                await on_message(ws, message)
        except KeyboardInterrupt:
            exit(0)
        except websockets.exceptions.ConnectionClosedOK:
            msg("WebSocket connection closed")
        except Exception as e:
            msg("(WebSocket) Error:", e)
            traceback.print_exc()


async def on_message(ws, message):
    global last_file, last_file_ext

    try:
        data = json.loads(message)
    except BaseException:
        return

    if data["type"] == "files":
        dta = data.get("data")

        if not dta:
            return

        if dta["name"] == username:
            return

        files = dta.get("files")

        if not files:
            return

        first = files[0]
        name = first.get("name")
        ext = first.get("extension")

        if (not name) or (not ext):
            return

        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webm", ".mp4"]:
            return

        last_file = f"https://deek.chat/storage/files/{name}"
        last_file_ext = ext
    elif data["type"] in ["message", "messageEnd"]:
        if blocked():
            return

        if data["data"]["name"] == username:
            return

        text = data["data"]["text"].strip()

        if not text.startswith(prefix):
            return

        room_id = data["roomId"]
        words = text.lstrip(prefix).split(" ")
        cmd = words[0]
        args = words[1:]

        if cmd in ["ping"]:
            update_time()
            await send_message(ws, "Pong!", room_id)

        elif cmd in ["help"]:
            update_time()
            await send_message(ws, f"Commands: describe | wins | numbers | date | bird | shitpost | who | when | write", room_id)

        elif cmd in ["describe"]:
            if len(args) >= 1:
                update_time()
                arg = " ".join(clean_list(args))
                arg = clean_gifmaker(arg)
                await gif_describe(arg, room_id)

        elif cmd in ["wins", "win"]:
            if len(args) >= 1:
                update_time()
                arg = " ".join(clean_list(args))
                arg = clean_gifmaker(arg)
                await gif_wins(arg, room_id)
            else:
                update_time()
                await gif_wins(None, room_id)

        elif cmd in ["numbers", "number", "nums", "num"]:
            update_time()

            if len(args) > 0:
                arg = " ".join(clean_list(args))
            else:
                arg = None

            arg = clean_gifmaker(arg)
            await gif_numbers(arg, room_id)

        elif cmd in ["date", "data", "time", "datetime"]:
            update_time()
            await gif_date(room_id)

        elif cmd in ["who", "pick", "any", "user", "username"]:
            update_time()

            if len(args) > 0:
                arg = " ".join(clean_list(args))
            else:
                arg = None

            await gif_user(arg, room_id)

        elif cmd in ["when", "die", "death"]:
            update_time()

            if len(args) > 0:
                arg = " ".join(clean_list(args))
            else:
                arg = None

            await gif_when(arg, room_id)

        elif cmd in ["bird", "birds", "birb", "birbs", "brb"]:
            update_time()
            await random_bird(ws, room_id)

        elif cmd in ["post", "shitpost", "4chan", "anon", "shit"]:
            update_time()
            await shitpost(ws, room_id)

        elif cmd in ["write", "writer", "words", "text", "meme"]:
            update_time()

            if len(args) > 0:
                arg = " ".join(clean_list(args))
                arg = clean_gifmaker(arg)
            else:
                arg = None

            await make_meme(ws, arg, room_id)

        elif cmd in ["video", "vid"]:
            update_time()

            if len(args) > 0:
                arg = " ".join(clean_list(args))
                arg = clean_gifmaker(arg)
            else:
                arg = None

            await make_video(ws, arg, room_id)


async def make_video(ws, arg, room_id):
    if not last_file:
        return

    try:
        url = last_file

        await send_message(ws, "Generating video...", room_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                with tempfile.NamedTemporaryFile(delete=False, suffix=last_file_ext) as temp_file:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        temp_file.write(chunk)

                file_name = temp_file.name

                words = arg if arg else ""

                if words == "random":
                    words = "[Random] [Random]"

                command = gifmaker_command([
                    "--input", file_name,
                    "--words", words,
                    "--filter", "anyhue2",
                    "--opacity", 0.8,
                    "--fontsize", 60,
                    "--delay", 600,
                    "--padding", 30,
                    "--fontcolor", "light2",
                    "--bgcolor", "black",
                    "--bottom", 30,
                    "--font", "nova",
                    "--frames", 18,
                    "--fillgen",
                    "--word-color-mode", "random",
                    "--width", 600,
                    "--output", "/tmp/gifmaker.webm",
                ])

                await run_gifmaker(command, room_id)
                os.remove(file_name)

    except Exception as e:
        print("Error:", e)
        return None


async def make_meme(ws, arg, room_id):
    if not last_file:
        return

    try:
        url = last_file

        await send_message(ws, "Generating gif...", room_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                with tempfile.NamedTemporaryFile(delete=False, suffix=last_file_ext) as temp_file:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        temp_file.write(chunk)

                file_name = temp_file.name

                words = arg if arg else ""

                if words == "random":
                    words = "[Random] [Random]"

                command = gifmaker_command([
                    "--input", file_name,
                    "--words", words,
                    "--filter", "anyhue2",
                    "--opacity", 0.8,
                    "--fontsize", 60,
                    "--delay", 700,
                    "--padding", 30,
                    "--fontcolor", "light2",
                    "--bgcolor", "black",
                    "--bottom", 30,
                    "--font", "nova",
                    "--frames", 3,
                    "--fillgen",
                    "--word-color-mode", "random",
                ])

                await run_gifmaker(command, room_id)
                os.remove(file_name)

    except Exception as e:
        print("Error:", e)
        return None


async def random_bird(ws, room_id):
    birdfile = get_path("data/aves.txt")

    async with aiofiles.open(birdfile, mode="r", encoding="utf-8") as file:
        birds = await file.readlines()
        bird = random.choice(birds).strip()
        await send_message(ws, f".i \"{bird}\" bird", room_id)


async def gif_describe(who, room_id):
    command = gifmaker_command([
        "--input", get_path("describe.jpg"),
        "--words", f"{who} is\\n[Random] [x5]",
        "--filter", "anyhue2",
        "--opacity", 0.8,
        "--fontsize", 66,
        "--delay", 700,
        "--padding", 50,
        "--fontcolor", "light2",
        "--bgcolor", "black",
    ])

    await run_gifmaker(command, room_id)


async def gif_wins(who, room_id):
    if not who:
        who = random.choice(userlist)

    command = gifmaker_command([
        "--input", get_path("wins.gif"),
        "--words", f"{who} wins a ; [repeat] ; [RANDOM] ; [repeat]",
        "--bgcolor", "0,0,0",
        "--bottom", 20,
        "--filter", "anyhue2",
        "--framelist", "11,11,33,33",
        "--fontsize", 42,
    ])

    await run_gifmaker(command, room_id)


async def gif_numbers(arg, room_id):
    num = -1

    if arg:
        nums = extract_range(arg)

        if nums[0] is not None:
            if nums[1] is not None:
                if nums[0] < nums[1]:
                    num = random_int(nums[0], nums[1])
                else:
                    return
            else:
                num = random_int(0, nums[0])

        if num == -1:
            num = string_to_number(arg)

    if num == -1:
        num = random_int(0, 999)

    command = gifmaker_command([
        "--input", get_path("numbers.pnf"),
        "--top", 20,
        "--words", num,
        "--fontcolor", "0,0,0",
        "--fontsize", 66,
        "--format", "jpg",
    ])

    await run_gifmaker(command, room_id)


async def gif_date(room_id):
    command = gifmaker_command([
        "--input", get_path("time.jpg"),
        "--words", "Date: [date %A %d] ; [repeat] ; Time: [date %I:%M %p] ; [repeat]",
        "--filter", "anyhue2",
        "--bottom", 20,
        "--bgcolor", "0,0,0",
        "--fontsize", 80,
    ])

    await run_gifmaker(command, room_id)


async def gif_user(who, room_id):
    if not who:
        who = random.choice(userlist)

    what = random.choice(["based", "cringe"])

    command = gifmaker_command([
        "--input", get_path("nerd.jpg"),
        "--words", f"{who} is [x2] ; {what} [x2]",
        "--filter", "anyhue2",
        "--bottom", 20,
        "--fontcolor", "light2",
        "--bgcolor", "darkfont2",
        "--outline", "font",
        "--deepfry",
        "--font", "nova",
        "--fontsize", 45,
        "--opacity", 0.8,
    ])

    await run_gifmaker(command, room_id)


async def gif_when(who, room_id):
    if not who:
        who = random.choice(userlist)

    date = random_date()

    command = gifmaker_command([
        "--input", get_path("sky.jpg"),
        "--words", f"{who} will die [x2] ; {date} [x2]",
        "--filter", "anyhue2",
        "--bottom", 66,
        "--fontcolor", "light2",
        "--bgcolor", "darkfont2",
        "--outline", "font",
        "--font", "nova",
        "--fontsize", 70,
        "--opacity", 0.8,
        "--wrap", 25,
    ])

    await run_gifmaker(command, room_id)


async def shitpost(ws, room_id):
    boards = ["g", "an", "ck", "lit", "x", "tv", "v", "fit", "k", "o"]
    board = random.choice(boards)

    try:
        threads_url = f"https://a.4cdn.org/{board}/threads.json"
        async_client = httpx.AsyncClient()
        threads_response = await async_client.get(threads_url)
        threads_response.raise_for_status()
        threads_json = threads_response.json()
        threads = threads_json[0]["threads"]

        # Select a random thread
        id = threads[random_int(0, len(threads) - 1)]["no"]
        thread_url = f"https://a.4cdn.org/{board}/thread/{id}.json"

        # Fetch the selected thread
        thread_response = await async_client.get(thread_url)
        thread_response.raise_for_status()
        thread_json = thread_response.json()
        posts = thread_json["posts"]

        # Select a random post
        post = posts[random_int(0, len(posts) - 1)]
        number = post.get("no", "")
        html = post.get("com", "")

        if not html:
            return

        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Remove elements with class "quotelink"
        for elem in soup.select(".quotelink"):
            elem.decompose()

        # Replace <br> with newline
        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Get the text content
        text = soup.get_text(separator="\n").strip()
        text = clean_lines(text)
        url = f">boards.4chan.org/{board}/thread/{id}#p{number}"

        if not text:
            text = url
        else:
            text = f"{text}\n{url}"

        await send_message(ws, text, room_id)

    except Exception as err:
        msg(f"Error: {err}")


async def run_gifmaker(command, room_id):
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        shell=True,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        msg(f"(Process) Error: {stderr.decode()}")
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
    ext = "jpeg" if ext == "jpg" else ext
    url = "https://deek.chat/message/send/" + str(room_id)

    data = aiohttp.FormData()

    if ext in ["webm", "mp4"]:
        ctype = f"video/{ext}"
    else:
        ctype = f"image/{ext}"

    data.add_field(name="files[]", value=open(path, "rb"), filename=path.name, content_type=ctype)

    try:
        async with aiohttp.ClientSession(cookies=cookies) as sess:
            async with sess.post(url, data=data, headers={}) as response:
                await response.text()
    except Exception as e:
        msg(f"(Upload) Error: {e}")
        traceback.print_exc()

    remove_file(path)


async def send_message(ws, text, room_id):
    await ws.send(json.dumps({"type": "message", "data": text, "roomId": room_id}))

while True:
    try:
        auth()
        msg("Authenticated")
        asyncio.run(run())
    except KeyboardInterrupt:
        break
    except Exception as e:
        msg("(Main) Error:", e)
        traceback.print_exc()
