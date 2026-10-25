"""Turns a post (slides JSON) into 1080x1080 PNG carousel images with Playwright.

Variety comes from three independent choices: the palette (picked by Claude to fit the
topic), the background style and the alignment (picked from the post seed so consecutive
posts look different), and the layout of each slide."""
import base64
import html
import pathlib
import re

LAYOUTS = ("hero", "points", "cards", "quote", "code")
BACKGROUNDS = ("glow", "rings", "grid", "diagonal")

#            base gradient stops               glow                    glow2                   accent     ink        muted
PALETTES = {
    "claude_orange": ("#2A130C", "#170905", "#0C0403", "rgba(217,119,87,.55)", "rgba(160,60,25,.45)", "#FFB27A", "#FFF7F0", "#F2D3C2"),
    "cyber_blue":    ("#0A3FB5", "#06246E", "#020B2A", "rgba(47,123,255,.85)", "rgba(20,80,255,.55)", "#7FD1FF", "#F4F8FF", "#B9CBEA"),
    "matrix_green":  ("#0B3D2A", "#06231A", "#020C08", "rgba(40,200,120,.50)", "rgba(10,120,70,.45)", "#6CF0A8", "#F2FFF7", "#B5DCC6"),
    "alert_red":     ("#5A0D12", "#2A0508", "#0E0203", "rgba(255,60,60,.50)",  "rgba(150,10,20,.50)", "#FF8A80", "#FFF5F5", "#EBC2C2"),
    "ai_violet":     ("#3B1C8C", "#1E0E4D", "#0A0420", "rgba(140,90,255,.60)", "rgba(80,40,200,.50)", "#C9B2FF", "#F7F3FF", "#CFC4EE"),
    "code_teal":     ("#0D4C55", "#062A30", "#021114", "rgba(40,200,210,.50)", "rgba(10,110,130,.50)", "#7DEBF0", "#F0FEFF", "#B4DADD"),
    "study_gold":    ("#5A3A06", "#2D1C03", "#120B01", "rgba(255,190,60,.50)", "rgba(170,100,10,.45)", "#FFD27A", "#FFFAF0", "#EADCC0"),
}

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1080px;background:#000}
body{font-family:"Inter","Helvetica Neue",Arial,"Noto Sans",sans-serif;-webkit-font-smoothing:antialiased}
.slide{width:1080px;height:1080px;position:relative;overflow:hidden;color:var(--ink)}
.slide::before,.slide::after{content:"";position:absolute;inset:0;pointer-events:none}
.content{position:absolute;left:90px;right:90px;top:84px;bottom:170px;display:flex;flex-direction:column;justify-content:center;overflow:hidden;z-index:1}
.align-center .content{align-items:center;text-align:center;justify-content:center}
.mark{height:calc(130px*var(--s));width:auto;max-width:300px;object-fit:contain;margin-bottom:calc(30px*var(--s));align-self:flex-start}
.align-center .mark{align-self:center}
.kicker{font-size:calc(26px*var(--s));letter-spacing:.18em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:calc(var(--t)*var(--s));line-height:1.02;font-weight:900;letter-spacing:-.02em;margin-top:calc(22px*var(--s));text-shadow:0 8px 50px rgba(0,0,0,.35);overflow-wrap:break-word}
h1 em{font-style:normal;color:var(--accent)}
.lead{font-size:calc(40px*var(--s));line-height:1.38;color:var(--muted);margin-top:calc(34px*var(--s));max-width:880px}
.points{list-style:none;margin-top:calc(44px*var(--s));display:flex;flex-direction:column;gap:calc(26px*var(--s));text-align:left}
.points li{display:flex;gap:calc(24px*var(--s));align-items:flex-start;font-size:calc(36px*var(--s));line-height:1.32;color:var(--muted)}
.points b{color:var(--ink)}
.num{flex:0 0 auto;width:calc(58px*var(--s));height:calc(58px*var(--s));border-radius:50%;border:2px solid var(--accent);background:var(--chip);color:var(--accent);font-weight:800;font-size:calc(26px*var(--s));display:flex;align-items:center;justify-content:center;box-shadow:0 0 28px var(--chip)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:calc(48px*var(--s));width:100%;text-align:left}
.cards.n2,.cards.n4{grid-template-columns:repeat(2,1fr)}
.card{background:var(--card);border:1.5px solid var(--line);border-radius:26px;padding:calc(28px*var(--s)) calc(24px*var(--s))}
.card .n{font-size:calc(24px*var(--s));font-weight:800;color:var(--accent);margin-bottom:12px}
.card b{display:block;font-size:calc(30px*var(--s));line-height:1.2;margin-bottom:10px}
.card p{font-size:calc(24px*var(--s));line-height:1.38;color:var(--muted)}
.quote{margin-top:calc(40px*var(--s));padding:calc(36px*var(--s)) calc(40px*var(--s));border-left:8px solid var(--accent);background:var(--card);border-radius:0 24px 24px 0;text-align:left;max-width:900px}
.quote p{font-size:calc(44px*var(--s));line-height:1.3;font-weight:600}
.quote span{display:block;margin-top:18px;font-size:calc(26px*var(--s));color:var(--muted)}
.code{margin-top:calc(34px*var(--s));width:100%;text-align:left;background:rgba(0,0,0,.45);border:1.5px solid var(--line);border-radius:22px;overflow:hidden}
.code .bar{display:flex;gap:10px;padding:16px 22px;border-bottom:1px solid var(--line)}
.code .bar i{width:14px;height:14px;border-radius:50%;background:var(--line)}
.code .bar i:first-child{background:var(--accent)}
.code pre{padding:calc(26px*var(--s)) calc(28px*var(--s));font-family:"JetBrains Mono","DejaVu Sans Mono",Menlo,monospace;font-size:calc(30px*var(--s));line-height:1.45;color:var(--ink);white-space:pre-wrap;word-break:break-word}
.footer{position:absolute;left:90px;right:90px;bottom:60px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--line);padding-top:26px;z-index:1}
.brand{display:flex;align-items:center;gap:16px;font-size:28px;font-weight:700}
.brand img{width:52px;height:52px;object-fit:contain;filter:invert(1)}
.page{display:flex;align-items:center;gap:10px}
.page i{width:12px;height:12px;border-radius:6px;background:var(--line)}
.page i.on{width:34px;background:var(--accent)}

/* backgrounds */
.bg-glow{background:radial-gradient(900px 700px at 8% 0%,var(--glow),transparent 60%),radial-gradient(800px 700px at 100% 100%,var(--glow2),transparent 60%),linear-gradient(160deg,var(--b1),var(--b2) 50%,var(--b3))}
.bg-glow::before{inset:-20%;background:conic-gradient(from 200deg at 30% 40%,transparent 0deg,rgba(255,255,255,.14) 40deg,transparent 90deg,transparent 360deg);filter:blur(30px)}
.bg-rings{background:radial-gradient(700px 600px at 78% 22%,var(--glow),transparent 65%),radial-gradient(700px 600px at 0% 100%,var(--glow2),transparent 60%),linear-gradient(200deg,var(--b1),var(--b2) 55%,var(--b3))}
.bg-rings::before{background:repeating-radial-gradient(circle at 78% 22%,transparent 0 68px,rgba(255,255,255,.07) 68px 70px);-webkit-mask-image:radial-gradient(circle at 78% 22%,#000 0%,transparent 70%);mask-image:radial-gradient(circle at 78% 22%,#000 0%,transparent 70%)}
.bg-grid{background:radial-gradient(800px 640px at 50% 0%,var(--glow),transparent 65%),radial-gradient(700px 500px at 100% 100%,var(--glow2),transparent 60%),linear-gradient(180deg,var(--b1),var(--b2) 50%,var(--b3))}
.bg-grid::before{opacity:.14;background-image:linear-gradient(rgba(255,255,255,.7) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.7) 1px,transparent 1px);background-size:60px 60px;-webkit-mask-image:radial-gradient(circle at 50% 20%,#000 0%,transparent 72%);mask-image:radial-gradient(circle at 50% 20%,#000 0%,transparent 72%)}
.bg-diagonal{background:radial-gradient(900px 700px at 100% 0%,var(--glow),transparent 60%),radial-gradient(700px 600px at 0% 100%,var(--glow2),transparent 60%),linear-gradient(135deg,var(--b2),var(--b1) 45%,var(--b3))}
.bg-diagonal::before{background:repeating-linear-gradient(135deg,rgba(255,255,255,.045) 0 2px,transparent 2px 26px)}
.bg-diagonal::after{background:radial-gradient(circle at 50% 50%,transparent 55%,rgba(0,0,0,.45) 100%)}
"""


def _clean(text) -> str:
    return _EMOJI.sub("", str(text or "")).strip()


def _esc(text) -> str:
    return html.escape(_clean(text))


def _title_html(title: str, accent: str) -> str:
    t = _esc(title)
    a = _esc(accent)
    if a and a in t:
        t = t.replace(a, f"<em>{a}</em>", 1)
    return t


def _title_size(title: str) -> int:
    n = len(_clean(title))
    for limit, size in ((12, 124), (20, 108), (30, 94), (42, 82)):
        if n <= limit:
            return size
    return 72


def _data_uri(path: pathlib.Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _layout_html(s: dict) -> str:
    layout = s.get("layout")
    if layout == "points":
        items = "".join(
            f'<li><span class="num">{i}</span><span><b>{_esc(p.get("title"))}</b> {_esc(p.get("text"))}</span></li>'
            for i, p in enumerate(s.get("points", [])[:4], 1))
        return f'<ul class="points">{items}</ul>'
    if layout == "cards":
        pts = s.get("points", [])[:4]
        items = "".join(
            f'<div class="card"><div class="n">{i:02d}</div><b>{_esc(p.get("title"))}</b><p>{_esc(p.get("text"))}</p></div>'
            for i, p in enumerate(pts, 1))
        return f'<div class="cards n{len(pts)}">{items}</div>'
    if layout == "quote":
        src = f"<span>{_esc(s.get('source'))}</span>" if s.get("source") else ""
        return f'<div class="quote"><p>{_esc(s.get("body"))}</p>{src}</div>'
    if layout == "code":
        lead = f'<p class="lead">{_esc(s.get("body"))}</p>' if s.get("body") else ""
        code = html.escape(str(s.get("code", "")).rstrip())
        return f'{lead}<div class="code"><div class="bar"><i></i><i></i><i></i></div><pre>{code}</pre></div>'
    return f'<p class="lead">{_esc(s.get("body"))}</p>' if s.get("body") else ""


def slide_html(s, idx, total, palette, bg, center, mark_uri, logo_uri, brand_text) -> str:
    b1, b2, b3, glow, glow2, accent, ink, muted = PALETTES[palette]
    align = "center" if center and s.get("layout") in ("hero", "quote") else "left"
    style = (f"--s:1;--t:{_title_size(s.get('title'))}px;--b1:{b1};--b2:{b2};--b3:{b3};--glow:{glow};"
             f"--glow2:{glow2};--accent:{accent};--ink:{ink};--muted:{muted};"
             "--card:rgba(255,255,255,.07);--line:rgba(255,255,255,.22);--chip:rgba(255,255,255,.10)")
    mark = f'<img class="mark" src="{mark_uri}" alt="">' if (mark_uri and idx == 0) else ""
    kicker = f'<div class="kicker">{_esc(s.get("kicker"))}</div>' if s.get("kicker") else ""
    dots = "".join(f'<i class="{"on" if i == idx else ""}"></i>' for i in range(total))
    return f"""<!doctype html><html lang="uz"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><section class="slide bg-{bg} align-{align}" style="{style}">
<div class="content">{mark}{kicker}<h1>{_title_html(s.get('title'), s.get('accent'))}</h1>{_layout_html(s)}</div>
<div class="footer"><div class="brand"><img src="{logo_uri}" alt="">{html.escape(brand_text)}</div><div class="page">{dots}</div></div>
</section></body></html>"""


def render_post(post: dict, out_dir: pathlib.Path, seed: int, assets: pathlib.Path, brand_text: str = ""):
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    palette = post.get("palette") if post.get("palette") in PALETTES else "cyber_blue"
    bg = BACKGROUNDS[seed % len(BACKGROUNDS)]
    center = (seed // len(BACKGROUNDS)) % 2 == 1
    logo_uri = _data_uri(assets / "logo.png")
    mark_path = assets / "marks" / f"{post.get('brand_mark')}.png"
    mark_uri = _data_uri(mark_path) if post.get("brand_mark") and mark_path.exists() else None

    slides = post["slides"][:10]
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        for i, s in enumerate(slides):
            page.set_content(slide_html(s, i, len(slides), palette, bg, center, mark_uri, logo_uri, brand_text),
                             wait_until="load")
            page.evaluate("document.fonts.ready")
            # Shrink everything a little at a time until nothing overflows the content box
            # (so a long title can never run under the logo, footer or another element).
            scale = 1.0
            for _ in range(8):
                overflow = page.evaluate(
                    "() => { const c = document.querySelector('.content');"
                    " return c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1; }")
                if not overflow:
                    break
                scale *= 0.9
                page.evaluate(f"document.querySelector('.slide').style.setProperty('--s', '{scale:.3f}')")
            path = out_dir / f"slide-{i + 1}.png"
            page.locator(".slide").screenshot(path=str(path))
            paths.append(path)
        browser.close()
    return paths
