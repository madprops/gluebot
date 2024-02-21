<img src="bot.jpg" width="360">

---

## Installation

```shell
python -m venv venv
```

```shell
venv/bin/pip install -r requirements.txt
```

---

## Running

Credentials are read from the environment.

They're not stored in files.

```shell
env GLUEBOT_USERNAME="yourUsername" GLUEBOT_PASSWORD="yourPassword" venv/bin/python main.py
```

---

## Configuration

Modify `main.py` itself to edit what you need.

Set the path to `gifmaker` and maybe change the `prefix`.

By default it points to `/usr/bin/gifmaker`.

---

## Files

Files generated through commands are stored in `/tmp/gifmaker` and removed after they're done uploading.

---

## Commands

> ,ping

> ,describe Nick

> ,wins Nick

> ,numbers

> ,date