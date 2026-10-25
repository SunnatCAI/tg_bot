"""Minimal Telegram Bot API client (only what this project needs)."""
import json
import os

import requests


class TelegramError(RuntimeError):
    pass


class TG:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, files=None, **params):
        data = {}
        for key, value in params.items():
            if value is None:
                continue
            data[key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, bool)) else value
        resp = requests.post(self.base + method, data=data, files=files, timeout=90)
        try:
            body = resp.json()
        except ValueError:
            raise TelegramError(f"{method}: HTTP {resp.status_code}")
        if not body.get("ok"):
            raise TelegramError(f"{method}: {body.get('description')}")
        return body["result"]

    def send_album(self, chat_id, photos, caption=None):
        """Send 1..10 photos. Each item is a local file path or a Telegram file_id.
        The caption goes on the first photo (Telegram shows it under the album).
        Always returns a list of sent messages."""
        if not 1 <= len(photos) <= 10:
            raise ValueError("Telegram albomida 1 dan 10 tagacha rasm bo'ladi")
        files, opened = {}, []
        media = []
        try:
            for i, item in enumerate(photos):
                if os.path.exists(str(item)):
                    key = f"p{i}"
                    fh = open(item, "rb")
                    opened.append(fh)
                    files[key] = fh
                    ref = f"attach://{key}"
                else:
                    ref = item
                entry = {"type": "photo", "media": ref}
                if i == 0 and caption:
                    entry["caption"] = caption
                    entry["parse_mode"] = "HTML"
                media.append(entry)

            if len(media) == 1:
                single = media[0]
                photo = files.get("p0") or single["media"]
                params = dict(chat_id=chat_id, caption=single.get("caption"),
                              parse_mode=single.get("parse_mode"))
                if "p0" in files:
                    msg = self.call("sendPhoto", files={"photo": photo}, **params)
                else:
                    msg = self.call("sendPhoto", photo=photo, **params)
                return [msg]
            return self.call("sendMediaGroup", files=files or None, chat_id=chat_id, media=media)
        finally:
            for fh in opened:
                fh.close()

    def try_call(self, method, **params):
        """Same as call() but never raises; used for cosmetic updates."""
        try:
            return self.call(method, **params)
        except Exception as exc:  # noqa: BLE001
            print(f"[ogohlantirish] {method} bajarilmadi: {exc}")
            return None
