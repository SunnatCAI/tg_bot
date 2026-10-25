"""Entry point.

  python -m bot.main run --schedule "<cron>"          # what GitHub Actions calls on a schedule
  python -m bot.main run --slot morning --stage draft  # manual run
  python -m bot.main whoami                            # print chat IDs the bot can see
  python -m bot.main preview [file.json]               # render slides locally, no Telegram/Claude
"""
import argparse
import datetime
import html
import json
import os
import pathlib
import zlib

from . import config, content, render
from .telegram import TG

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
STATE = ROOT / "state"
DRAFTS = STATE / "drafts"
HISTORY = STATE / "history.json"
OUT = ROOT / "out"
TZ = datetime.timezone(datetime.timedelta(hours=config.TZ_OFFSET_HOURS))


def today() -> str:
    return datetime.datetime.now(TZ).date().isoformat()


def load_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return default


def save_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def available_marks():
    return sorted(p.stem for p in (ASSETS / "marks").glob("*.png"))


def brand_text(cfg) -> str:
    label = os.environ.get("CHANNEL_LABEL", "").strip()
    if label:
        return label
    return cfg.channel_id if cfg.channel_id.startswith("@") else ""


def remember(slot: str, post: dict) -> None:
    history = load_json(HISTORY, [])
    history.append({"date": today(), "slot": slot, "topic": post.get("topic", "")})
    save_json(HISTORY, history[-60:])


def publish_to_channel(tg: TG, cfg, post: dict, media) -> None:
    tg.send_album(cfg.channel_id, media, post["caption"])
    poll = post.get("poll")
    if poll:
        tg.call("sendPoll", chat_id=cfg.channel_id, question=poll["question"],
                options=[{"text": o} for o in poll["options"]], is_anonymous=True)


def approval_text(slot: str, post: dict, status: str = "", auto: bool = False) -> str:
    post_time = config.SLOTS[slot][0]
    lines = [f"<b>Qoralama: {config.SLOT_NAMES_UZ[slot]}</b> · {today()} {post_time}",
             f"Mavzu: <code>{html.escape(post.get('topic', ''))}</code>"]
    if post.get("poll"):
        opts = "\n".join(f"• {html.escape(o)}" for o in post["poll"]["options"])
        lines.append(f"\nSoʻrovnoma: {html.escape(post['poll']['question'])}\n{opts}")
    if post.get("sources"):
        src = ", ".join(f'<a href="{html.escape(s.get("url", ""))}">{html.escape(s.get("name", "manba"))}</a>'
                        for s in post["sources"][:5] if s.get("url"))
        if src:
            lines.append(f"\nManbalar: {src}")
    if auto:
        default = f"{post_time} da avtomatik chiqadi. Toʻxtatish uchun ❌ bosing."
    else:
        default = (f"{post_time} gacha ✅ bossangiz kanalga chiqadi. "
                   "Bosmasangiz yoki ❌ bossangiz, post oʻtkazib yuboriladi.")
    lines.append("\n" + (status or default))
    return "\n".join(lines)


def cmd_draft(cfg, tg: TG, slot: str, generate=content.generate) -> dict:
    draft_id = f"{today()}-{slot}"
    history = load_json(HISTORY, [])
    post = generate(cfg, slot, [h["topic"] for h in history[-30:]], available_marks(), today())
    seed = zlib.crc32(draft_id.encode())
    paths = render.render_post(post, OUT / draft_id, seed, ASSETS, brand_text(cfg))
    draft = {"id": draft_id, "slot": slot, "post": post, "status": "pending", "approval": cfg.approval}

    # The draft always goes to the admin first. With APPROVAL on it needs a ✅;
    # with APPROVAL off it goes out on time unless the admin presses ❌.
    sent = tg.send_album(cfg.admin_chat_id, [str(p) for p in paths], post["caption"])
    # Reuse the uploaded photos for the channel later, so nothing has to be stored in the repo.
    draft["file_ids"] = [m["photo"][-1]["file_id"] for m in sent]
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Joylash", "callback_data": f"ok:{draft_id}"},
        {"text": "❌ Bekor qilish", "callback_data": f"no:{draft_id}"},
    ]]}
    ctrl = tg.call("sendMessage", chat_id=cfg.admin_chat_id, text=approval_text(slot, post, auto=not cfg.approval),
                   parse_mode="HTML", reply_markup=keyboard, link_preview_options={"is_disabled": True})
    draft["control_message_id"] = ctrl["message_id"]
    save_json(DRAFTS / f"{draft_id}.json", draft)
    print(f"Qoralama yuborildi: {draft_id}")
    return draft


def find_decision(tg: TG, admin_chat_id: str, draft_id: str):
    """Button presses wait on Telegram's side for up to 24h, so a job that runs
    later can still read them. The last press from the admin wins."""
    decision = None
    updates = tg.call("getUpdates", allowed_updates=["callback_query"], timeout=0, limit=100)
    for upd in updates:
        cq = upd.get("callback_query") or {}
        if str(cq.get("from", {}).get("id")) != str(admin_chat_id):
            continue
        data = cq.get("data", "")
        if data in (f"ok:{draft_id}", f"no:{draft_id}"):
            decision = data.split(":", 1)[0]
    return decision


def cmd_publish(cfg, tg: TG, slot: str) -> str:
    draft_id = f"{today()}-{slot}"
    path = DRAFTS / f"{draft_id}.json"
    draft = load_json(path, None)
    if not draft:
        print(f"Qoralama topilmadi: {draft_id}")
        return "missing"
    if draft.get("status") != "pending":
        print(f"Qoralama allaqachon: {draft.get('status')}")
        return draft.get("status")

    decision = find_decision(tg, cfg.admin_chat_id, draft_id)
    post = draft["post"]
    needs_ok = draft.get("approval", True)
    if decision == "ok" or (decision is None and not needs_ok):
        publish_to_channel(tg, cfg, post, draft["file_ids"])
        draft["status"] = "published"
        remember(slot, post)
        note = "✅ Kanalga joylandi."
    else:
        draft["status"] = "rejected" if decision == "no" else "skipped"
        note = "❌ Bekor qilindi." if decision == "no" else "⏭ Tasdiqlanmadi, oʻtkazib yuborildi."
    tg.try_call("editMessageText", chat_id=cfg.admin_chat_id, message_id=draft.get("control_message_id"),
                text=approval_text(slot, post, note), parse_mode="HTML",
                link_preview_options={"is_disabled": True})
    save_json(path, draft)
    print(f"{draft_id}: {draft['status']}")
    return draft["status"]


def cmd_whoami(cfg, tg: TG) -> None:
    updates = tg.call("getUpdates", allowed_updates=["message", "channel_post", "my_chat_member"], timeout=0)
    seen = {}
    for upd in updates:
        for key in ("message", "channel_post", "my_chat_member"):
            chat = (upd.get(key) or {}).get("chat")
            if chat:
                seen[chat["id"]] = f"{chat.get('type')}: {chat.get('title') or chat.get('username') or chat.get('first_name')}"
    if not seen:
        print("Hech narsa topilmadi. Botga shaxsiy xabarda /start yozing va qayta ishga tushiring.")
    for chat_id, label in seen.items():
        print(f"{chat_id}\t{label}")


def cmd_preview(sample: pathlib.Path) -> None:
    post = json.loads(sample.read_text("utf-8"))
    post = content.validate(post, "evening" if post.get("poll") else "noon", available_marks())
    paths = render.render_post(post, OUT / "preview", zlib.crc32(sample.name.encode()), ASSETS,
                               os.environ.get("CHANNEL_LABEL", ""))
    print("\n".join(str(p) for p in paths))
    print("\nCaption:\n" + post["caption"])


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--schedule", default="")
    run.add_argument("--slot", default="")
    run.add_argument("--stage", default="")
    sub.add_parser("whoami")
    prev = sub.add_parser("preview")
    prev.add_argument("file", nargs="?", default=str(ASSETS / "sample_post.json"))
    args = ap.parse_args()

    if args.cmd == "preview":
        cmd_preview(pathlib.Path(args.file))
        return
    if args.cmd == "whoami":
        cmd_whoami(None, TG(config._get("TELEGRAM_BOT_TOKEN", True)))
        return

    slot, stage = config.slot_from_schedule(args.schedule)
    slot, stage = slot or args.slot, stage or args.stage
    if slot not in config.SLOTS or stage not in ("draft", "publish", "whoami"):
        raise SystemExit(f"Noma'lum slot/bosqich: {slot!r} {stage!r}")
    if stage == "whoami":
        # Only the token is needed here: this is how you find ADMIN_CHAT_ID in the first place.
        cmd_whoami(None, TG(config._get("TELEGRAM_BOT_TOKEN", True)))
        return
    cfg = config.load(need_claude=(stage == "draft"))
    tg = TG(cfg.bot_token)
    if stage == "draft":
        cmd_draft(cfg, tg, slot)
    else:
        cmd_publish(cfg, tg, slot)


if __name__ == "__main__":
    main()
