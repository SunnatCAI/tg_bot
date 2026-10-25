"""Writes the post with Claude: research (web search), Uzbek copy, slide plan, then a
separate proofreading pass for Uzbek Latin spelling."""
import html
import json
import re

from .render import LAYOUTS, PALETTES

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 6}

SYSTEM = """You write posts for an Uzbek-language Telegram channel about cybersecurity, AI and programming.
Audience: Uzbek students and junior IT specialists. Tone: confident, clear, no hype, no clickbait lies.

LANGUAGE (strict):
- Everything the reader sees is in Uzbek, Latin script, following the official orthography.
- Use the modifier letter turned comma ʻ (U+02BB) in oʻ and gʻ (oʻzbek, gʻoya), and the modifier
  apostrophe ʼ (U+02BC) for the tutuq belgisi (maʼlumot, daʼvo, sanʼat). Never use plain ' or ` for these.
- Keep established technical terms in English when Uzbek readers use them (ransomware, phishing, prompt, API, 2FA).

ACCURACY AND SAFETY:
- News must come from web search results published in the last 72 hours. Cross-check with at least two sources.
  If something is only claimed (by hackers, by a company), say it is a daʼvo and not confirmed.
- Never invent numbers, quotes or names.
- Defensive and educational only: no working exploit code, no malware, no step-by-step attack instructions
  against real systems. Commands and code you show must be safe to run (e.g. checking, hardening, auditing).

SLIDES (the carousel carries the explanation; the caption is only a short summary):
- 3 to 6 slides. Slide 1 hooks the reader; the next slides explain step by step; the last slide gives
  the practical takeaway ("Nima qilish kerak?" style).
- Every slide: "layout" (one of: {layouts}), "kicker" (1-3 words, small label), "title" (max 6 words),
  "accent" (one word copied exactly from the title to highlight, or ""), plus the fields its layout uses:
  hero -> "body" (max 160 chars); points -> "points" (2-4 items, each {{"title": max 4 words, "text": max 90 chars}});
  cards -> "points" (exactly 3 items, each {{"title": max 2 words, "text": max 70 chars}});
  quote -> "body" (the quote, max 150 chars) and "source" (who said it);
  code -> "body" (max 110 chars) and "code" (max 8 lines, max 48 chars per line).
- Vary layouts within a post; do not use the same layout on every slide.
- "palette": pick one that matches the topic: {palettes}.
  claude_orange is for posts about Claude/Anthropic. alert_red is for breaches, attacks and warnings.
- "brand_mark": if the post is mainly about a company/product whose mark is available ({marks}), put its name,
  otherwise null. Never draw or describe other logos.

CAPTION (Telegram HTML, parse_mode=HTML):
- 250-700 characters. 2-3 short paragraphs. Start with one fitting emoji; use at most 3 emoji in total,
  only where they add meaning.
- Allowed tags only: <b>, <i>, <code>, <pre>, <blockquote>, <a href="...">.
- Links: never paste bare URLs. Write the site or product name and link it: <a href="https://claude.ai">Claude</a>.
- Commands, tool names, file paths and code the reader may copy go in <code>...</code> (or <pre> for several lines).
- Quotes or the single most important sentence go in <blockquote>...</blockquote>.
- Escape &, < and > in normal text.

OUTPUT: only one JSON object, no commentary before or after:
{{"topic": "short English slug of the subject", "palette": "...", "brand_mark": null,
  "slides": [...], "caption": "...", "sources": [{{"name": "...", "url": "..."}}]{poll_field}}}
"""

POLL_FIELD = ',\n  "poll": {"question": "max 200 chars, Uzbek", "options": ["2 to 5 options, each max 80 chars"]}'

SLOT_TASKS = {
    "morning": (
        "Ertalabki yangilik. Use web search to find the single most important cybersecurity or AI news story "
        "from the last 48 hours that matters to Uzbek IT readers. Explain what happened, the verified facts, "
        "what it means, and what readers should do."
    ),
    "noon": (
        "Kunduzgi qoʻllanma. A practical tutorial, tip or mini-lesson about AI tools, cybersecurity hygiene "
        "or programming. One concrete skill the reader can apply today. Prefer a code or points slide with a "
        "safe command or snippet. Use web search to confirm commands, versions and links are current."
    ),
    "evening": (
        "Kechki muhokama. Pick one debatable, current topic in AI, cybersecurity or IT careers and present both "
        "sides fairly in the slides. End the caption by inviting readers to vote and to discuss in the comments. "
        "Also return a poll whose options match the positions. Use web search for any facts you cite."
    ),
}


class ContentError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates = fenced[::-1] if fenced else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    raise ContentError("Claude javobidan JSON topilmadi")


def visible_len(caption: str) -> int:
    return len(html.unescape(re.sub(r"<[^>]+>", "", caption or "")))


def safe_caption(caption: str, limit: int = 1000) -> str:
    """Telegram caps photo captions at 1024 visible characters. If the model overshoots,
    fall back to plain text cut at a sentence boundary rather than sending broken HTML."""
    caption = (caption or "").strip()
    if visible_len(caption) <= limit:
        return caption
    plain = html.unescape(re.sub(r"<[^>]+>", "", caption))
    cut = plain[:limit]
    stop = max(cut.rfind(". "), cut.rfind("\n"))
    if stop > limit // 2:
        cut = cut[:stop + 1]
    return html.escape(cut.strip())


def validate(post: dict, slot: str, marks: list) -> dict:
    slides = post.get("slides")
    if not isinstance(slides, list) or not 2 <= len(slides) <= 8:
        raise ContentError("Slaydlar soni 2 dan 8 gacha bo'lishi kerak")
    for i, s in enumerate(slides):
        if not isinstance(s, dict) or not str(s.get("title", "")).strip():
            raise ContentError(f"{i + 1}-slaydda sarlavha yo'q")
        if s.get("layout") not in LAYOUTS:
            s["layout"] = "hero" if i == 0 else "points"
        if s["layout"] in ("points", "cards") and not s.get("points"):
            s["layout"] = "hero"
        if s["layout"] == "code" and not s.get("code"):
            s["layout"] = "hero"
    if post.get("palette") not in PALETTES:
        post["palette"] = "cyber_blue"
    if post.get("brand_mark") not in marks:
        post["brand_mark"] = None
    if not str(post.get("caption", "")).strip():
        raise ContentError("Post matni (caption) bo'sh")
    post["caption"] = safe_caption(post["caption"])
    post.setdefault("topic", "untitled")
    post.setdefault("sources", [])
    if slot == "evening":
        poll = post.get("poll") or {}
        options = [str(o).strip()[:100] for o in poll.get("options", []) if str(o).strip()]
        question = str(poll.get("question", "")).strip()[:300]
        if not question or not 2 <= len(options) <= 10:
            raise ContentError("Kechki post uchun so'rovnoma (poll) noto'g'ri")
        post["poll"] = {"question": question, "options": options}
    else:
        post.pop("poll", None)
    return post


def _text_of(resp) -> str:
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")


def proofread(client, model: str, post: dict) -> dict:
    """Second, cheaper pass that only fixes Uzbek spelling. Anything it should not touch
    (code, URLs, structure) is restored from the original afterwards."""
    prompt = (
        "Quyidagi JSON ichidagi oʻzbekcha matnlarning imlo, tinish belgilari va grammatikasini tuzat. "
        "Lotin alifbosi qoidalari: oʻ va gʻ uchun ʻ (U+02BB), tutuq belgisi uchun ʼ (U+02BC). "
        "Maʼnoni, uzunlikni, JSON tuzilmasini, HTML teglarini, havolalarni, kodni va inglizcha "
        "texnik atamalarni oʻzgartirma. Faqat tuzatilgan JSON obyektini qaytar.\n\n"
        + json.dumps(post, ensure_ascii=False)
    )
    try:
        resp = client.messages.create(model=model, max_tokens=6000,
                                      messages=[{"role": "user", "content": prompt}])
        fixed = extract_json(_text_of(resp))
    except Exception as exc:  # noqa: BLE001
        print(f"[ogohlantirish] imlo tekshiruvi o'tkazib yuborildi: {exc}")
        return post

    if not isinstance(fixed.get("slides"), list) or len(fixed["slides"]) != len(post["slides"]):
        print("[ogohlantirish] imlo tekshiruvi tuzilmani buzdi, asl matn qoldirildi")
        return post

    href = re.compile(r'href="([^"]+)"')
    if href.findall(fixed.get("caption", "")) != href.findall(post["caption"]):
        fixed["caption"] = post["caption"]
    for keep in ("topic", "palette", "brand_mark", "sources"):
        fixed[keep] = post.get(keep)
    for new, old in zip(fixed["slides"], post["slides"]):
        for keep in ("layout", "code"):
            if keep in old:
                new[keep] = old[keep]
        if old.get("accent") and old["accent"] not in str(new.get("title", "")):
            new["title"], new["accent"] = old["title"], old["accent"]
    return fixed


def generate(cfg, slot: str, recent_topics: list, marks: list, today: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_key)
    system = SYSTEM.format(
        layouts=", ".join(LAYOUTS),
        palettes=", ".join(PALETTES),
        marks=", ".join(marks) or "none",
        poll_field=POLL_FIELD if slot == "evening" else "",
    )
    recent = ", ".join(recent_topics) or "yoʻq"
    user = (
        f"Bugungi sana: {today} (Toshkent vaqti).\n"
        f"Vazifa: {SLOT_TASKS[slot]}\n"
        f"Yaqinda yoritilgan mavzular (takrorlama): {recent}.\n"
        "Return only the JSON object."
    )
    messages = [{"role": "user", "content": user}]
    resp = None
    for _ in range(5):
        resp = client.messages.create(model=cfg.writer_model, max_tokens=8000, system=system,
                                      messages=messages, tools=[WEB_SEARCH_TOOL])
        if resp.stop_reason != "pause_turn":
            break
        # Long web-search turns pause; hand the partial turn back so Claude continues.
        messages = [messages[0], {"role": "assistant", "content": resp.content}]

    post = validate(extract_json(_text_of(resp)), slot, marks)
    post = proofread(client, cfg.checker_model, post)
    return validate(post, slot, marks)
