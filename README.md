<img src="describe.jpg" width="360">

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

```sh
#!/usr/bin/env bash
/path/to/gifmaker/venv/bin/python /path/to/gifmaker/src/main.py
```

---

## Files

Files generated through commands are stored in `/tmp/gifmaker` and removed when uploaded.

---

## Commands

> ,ping

> ,describe Nick

> ,wins Nick

> ,numbers

> ,date