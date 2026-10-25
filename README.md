# Kanal bot

Telegram kanalga har kuni 3 ta post: **08:00** yangilik, **12:00** qoʻllanma, **18:00** muhokama + soʻrovnoma.
Server kerak emas, hammasi GitHub Actions'da ishlaydi. Matnni Claude yozadi, slaydlar avtomatik chiziladi.

## Qanday ishlaydi

| Vaqt (Toshkent) | Nima boʻladi |
|---|---|
| 06:15 / 10:15 / 16:15 | Qoralama tayyorlanadi va **sizga shaxsiy xabarda** keladi: karusel, matn, manbalar, ✅ / ❌ tugmalari |
| ~08:00 / ~12:00 / ~18:00 | Tugmangiz tekshiriladi va post kanalga chiqadi (18:00 da soʻrovnoma ham) |

- **Tasdiqlash rejimi** (`APPROVAL=1`, boshlangʻich): faqat ✅ bosilgan post chiqadi. Hech narsa bosmasangiz, post oʻtkazib yuboriladi.
- **Avtomatik rejim** (`APPROVAL=0`): qoralama baribir sizga keladi, lekin post oʻz vaqtida chiqadi. Toʻxtatish uchun ❌ bosasiz.

Tugmani bosganingizda Telegram bir oz "yuklanmoqda" koʻrsatishi mumkin, bu normal: bot doim ishlab turmaydi, bosilgan tugma post vaqtida oʻqiladi va xabar "✅ Kanalga joylandi" deb yangilanadi.

GitHub jadvali aniq emas: post 08:00 dan 5–15 daqiqa kechikib chiqishi mumkin.

## Sozlash (bir marta, ~15 daqiqa)

### 1. Yangi bot
1. Telegram'da **@BotFather** → `/newbot` → nom bering → **tokenni** saqlab qoʻying (hech kimga bermang, chatga yozmang).
2. **Alohida bot oching.** Boshqa ishlab turgan botingizni (masalan, test botingizni) ishlatmang: ikkalasi bir-biriga xalaqit beradi.
3. Botni kanalingizga **admin** qiling, "Post messages" huquqi bilan.
4. Botni Telegram'da oching va **/start** bosing (shunda u sizga qoralama yubora oladi).

### 2. GitHub repo
1. GitHub'da yangi **private** repo yarating.
2. Shu papkadagi hamma fayllarni yuklang (`.github` papkasi ham boʻlishi shart).

### 3. Maxfiy kalitlar
Repo → **Settings → Secrets and variables → Actions**.

**Secrets** (yashirin):
| Nomi | Qiymati |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather bergan token |
| `ANTHROPIC_API_KEY` | Claude API kaliti (console.anthropic.com) |
| `CHANNEL_ID` | Kanal: `@username` yoki `-100…` raqam |
| `ADMIN_CHAT_ID` | Sizning Telegram ID raqamingiz (pastdagi 4-qadam) |

**Variables** (ochiq):
| Nomi | Qiymati |
|---|---|
| `APPROVAL` | `1` (birinchi hafta), keyin `0` |
| `CHANNEL_LABEL` | Slayd pastida yoziladigan nom, masalan `@kanalingiz` |

### 4. ID raqamingizni topish
Repo → **Actions → kanal → Run workflow** → stage: `whoami` → Run.
Tugagach, logni oching: `private: Ism` yonidagi raqam sizning `ADMIN_CHAT_ID`. Uni secret'ga yozing.

### 5. Sinov
1. **Run workflow** → slot: `morning`, stage: `draft`. Bir necha daqiqada qoralama shaxsiy xabaringizga keladi.
2. ✅ bosing.
3. **Run workflow** → slot: `morning`, stage: `publish`. Post kanalga chiqadi.

Shundan keyin hammasi jadval boʻyicha oʻzi ishlaydi.

## Sozlashlar

- **Modellar:** postlarni `claude-sonnet-5-5` yozadi, imloni `claude-haiku-5-5` tekshiradi. Variables'da `WRITER_MODEL` / `CHECKER_MODEL` bilan oʻzgartirish mumkin.
- **Brend belgilari:** mavzu biror mahsulot haqida boʻlsa (masalan Claude), uning logotipi 1-slaydga qoʻyiladi. Logotiplar `assets/marks/<nom>.png` (shaffof fon). Yangisini qoʻshsangiz, Claude uni oʻzi taniydi. Faqat rasmiy, ishlatishga ruxsat berilgan fayllarni qoʻying.
- **Kanal logotipi:** `assets/logo.png` (qora, shaffof fon; slaydda oq boʻlib chiqadi).
- **Ranglar:** `bot/render.py` → `PALETTES`. Claude mavzuga qarab tanlaydi (Claude → olovrang, buzilish/hujum → qizil, va h.k.).
- **Mahalliy koʻrish:** `python -m bot.main preview` → `assets/sample_post.json` dan slaydlar `out/preview/` ga chiziladi.

## Muammolar

- **"Conflict: can't use getUpdates method while webhook is active"** → bu botga webhook ulangan. Alohida bot oching (1-qadam).
- **"chat not found"** → botga /start bosmagansiz yoki `ADMIN_CHAT_ID` notoʻgʻri.
- **"not enough rights"** → bot kanalda admin emas yoki post qilish huquqi yoʻq.
- **Holatni saqlash qadamida push xatosi** → Settings → Actions → General → Workflow permissions → **Read and write**.
- **Post chiqmadi** → Actions logini oching; `skipped` boʻlsa ✅ vaqtida bosilmagan.
