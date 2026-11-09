# -*- coding: utf-8 -*-
"""Құрылыс материалдарының калькуляторы - Telegram-бот.

Кітапхана: pyTelegramBotAPI (telebot).
Токен BOT_TOKEN атымен жүйелік ортадан немесе .env файлынан оқылады.
"""
import datetime
import math
import os
import re

# ---------------------------------------------------------------- деректер
MAX_TEXT = 300  # өте ұзын хабарламаның шегі

FAQ = [
    ("Бетон маркасы М200 деген не?",
     "М - бетонның орташа беріктігі (кгс/см²). М200 шамамен 200 кгс/см². "
     "Беріктік класымен салыстыру: В15 ≈ М200, В20 ≈ М250, В25 ≈ М350."),
    ("Бетонның тығыздығы қандай?",
     "Ауыр бетонның тығыздығы шамамен 2400 кг/м³. Сондықтан 1 м³ бетон "
     "шамамен 2,4 тонна тартады."),
    ("Бетон қанша уақытта қатады?",
     "Жобалық беріктікке бетон шамамен 28 тәулікте жетеді. 7 тәулікте "
     "беріктіктің шамамен 70% жиналады. Осы кезде бетонды ылғалды ұстау керек."),
    ("Қыста бетондауға бола ма?",
     "Ауа температурасы +5 °C-тан төмен болса, қосымша шаралар қажет: "
     "қыздыру, қысқы қоспалар, жылу оқшаулау. Қатып қалған бетон беріктіген жоғалтады."),
    ("Стандартты кірпіш өлшемі қандай?",
     "Қарапайым (бір еселі) кірпіш: 250 × 120 × 65 мм. Көлденең тігістің "
     "қалыңдығы әдетте шамамен 10 мм."),
    ("1 м² кірпіш қабырғаға неше кірпіш кетеді?",
     "Тігісті ескергенде: 0,5 кірпіш (120 мм) - 51 дана, 1 кірпіш (250 мм) - 102, "
     "1,5 кірпіш (380 мм) - 153, 2 кірпіш (510 мм) - 204 дана."),
    ("Плиткаға қанша қор алу керек?",
     "Түзу төсеуде шамамен 5-10%, диагональ немесе күрделі өрнекте 10-15%. "
     "Қор кесу мен сынуға кетеді."),
    ("Бояу шығынын қалай білуге болады?",
     "Банкада бір қабатқа арналған шығын жазылады. Су негізді бояу үшін ол "
     "көбіне 8-12 м²/л. Бетіне қарай шығын өзгереді, сондықтан алдымен "
     "банкадағы мәнді қараңыз."),
    ("Бояу алдында қабырғаны қалай дайындау керек?",
     "Шаң мен майдан тазалау, жарықтарды бітеу, грунттау және толық құрғату. "
     "Дайындықсыз бояу тез түсіп қалады және шығыны артады."),
    ("Неге қор (запас) қосылады?",
     "Қор өлшем қателігін, сынуды, кесуді және төгілуді өтейді: бетонға "
     "шамамен 5%, кірпішке 5%, плиткаға 10%, бояуға 10% қосамыз."),
]

TIPS = [
    "Материалды сатып алмас бұрын өлшемдерді екі рет өлшеңіз.",
    "Бетонды бір күнде үздіксіз құйған дұрыс: қабаттар арасында жік қалмайды.",
    "Плитканы бір партиядан алыңыз: әр партияның реңкі аздап өзгешеленеді.",
    "Бояу банкасындағы шығын мәнін қараңыз, ол есепті нақтылайды.",
    "Кірпішті қалау алдында ыстық күні сәл суландырыңыз, ерітіндіден суды тартып алмасын.",
    "Қор қосуды ұмытпаңыз: бетонға 5%, плиткаға 10%.",
    "Нақты жұмыс алдында есепті жоба мен нормативтік құжаттармен салыстырыңыз.",
]

BRICK_PER_M2 = {0.5: 51, 1.0: 102, 1.5: 153, 2.0: 204}
BRICK_THICK_M = {0.5: 0.12, 1.0: 0.25, 1.5: 0.38, 2.0: 0.51}
CONCRETE_DENSITY = 2400  # кг/м³

# ------------------------------------------------------ енгізуді тексеру
def parse_number(text, lo=0.0, hi=1000.0, allow_zero=False):
    """Мәтінді санға айналдырады. (мән, қате_хабары) қайтарады."""
    raw = (text or "").strip().replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None, "Сан енгізіңіз, мысалы: 2.5 (әріптерсіз)."
    if math.isnan(value) or math.isinf(value):
        return None, "Дұрыс сан енгізіңіз, мысалы: 2.5."
    if value < 0 or (value == 0 and not allow_zero):
        return None, "Сан нөлден үлкен болуы керек (теріс сан болмайды)."
    if value > hi:
        return None, f"Сан тым үлкен. Ең көбі {hi:g} енгізіңіз."
    if value < lo:
        return None, f"Сан кемінде {lo:g} болуы керек."
    return value, None


def parse_choice(text, options):
    value, err = parse_number(text, hi=100)
    if err or value not in options:
        shown = ", ".join(f"{o:g}" for o in options)
        return None, f"Мына мәндердің бірін енгізіңіз: {shown}."
    return value, None


def parse_tile(text):
    """'30x60' / '30 60' / '30х60' -> (30.0, 60.0) см."""
    parts = re.split(r"[xXхХ×*\s]+", (text or "").strip().replace(",", "."))
    parts = [p for p in parts if p]
    if len(parts) != 2:
        return None, "Өлшемді «30x60» түрінде (см) енгізіңіз."
    try:
        a, b = float(parts[0]), float(parts[1])
    except ValueError:
        return None, "Өлшемді «30x60» түрінде (см) енгізіңіз."
    if not (1 <= a <= 300 and 1 <= b <= 300):
        return None, "Плитка өлшемі 1-ден 300 см-ге дейін болуы керек."
    return (a, b), None


# ------------------------------------------------------------ есептеулер (ТҮЗЕТІЛГЕН)
def calc_concrete(d):
    vol = d["length"] * d["width"] * d["height"]
    total = vol * 1.05
    mass = total * CONCRETE_DENSITY / 1000
    return (f"🧱 Бетон көлемі\n"
            f"Таза көлем: {vol:.2f} м³\n"
            f"+5% қормен: {total:.2f} м³\n"
            f"Шамамен салмағы: {mass:.1f} т\n\n"
            f"Формула: V = ұзындық × ені × биіктік.")


def calc_brick(d):
    area = (d["length"] * d["height"]) - d["opening"]
    if area <= 0:
        return None
    t = d["thick"]
    pcs = area * BRICK_PER_M2[t]
    total = math.ceil(pcs * 1.05)
    vol = area * BRICK_THICK_M[t]
    return (f"🧱 Кірпіш есебі\n"
            f"Таза ауданы (тесіктерді шегергенде): {area:.2f} м²\n"
            f"Қалау көлемі: {vol:.2f} м³\n"
            f"Кірпіш саны: {math.ceil(pcs)} дана\n"
            f"+5% қормен: {total} дана\n\n"
            f"Норма: {BRICK_PER_M2[t]} дана/м² (кірпіш 250×120×65 мм, тігіс 10 мм).")


def calc_tile(d):
    a, b = d["tile"]
    room = d["length"] * d["width"]
    one = a * b / 10000
    pcs = math.ceil(room / one)
    total = math.ceil(room * 1.10 / one)
    return (f"🔲 Плитка есебі\n"
            f"Бөлме ауданы: {room:.2f} м²\n"
            f"Плитка {a:g}×{b:g} см: {pcs} дана\n"
            f"+10% қормен: {total} дана\n\n"
            f"Формула: көлем = аудан ÷ бір плитканың ауданы.")


def calc_paint(d):
    cons = d["cons"] if d["cons"] > 0 else 10.0
    litres = (d["area"] * d["coats"]) / cons
    total = litres * 1.10
    return (f"🎨 Бояу есебі\n"
            f"Ауданы: {d['area']:.2f} м², қабат саны: {d['coats']:g}\n"
            f"Шығын: {cons:g} м²/л\n"
            f"Бояу: {litres:.2f} л\n"
            f"+10% қормен: {total:.2f} л\n\n"
            f"Формула: литр = аудан × қабат ÷ шығын.")


# Диалог қадамдары: (кілт, сұрақ, тексеру функциясы)
def _num(hi=1000.0, allow_zero=False):
    return lambda t: parse_number(t, hi=hi, allow_zero=allow_zero)


CALCS = {
    "concrete": {
        "title": "Бетон",
        "steps": [
            ("length", "1/3. Ұзындығы (м)?", _num(500)),
            ("width", "2/3. Ені (м)?", _num(500)),
            ("height", "3/3. Қалыңдығы немесе биіктігі (м)?", _num(50)),
        ],
        "compute": calc_concrete,
    },
    "brick": {
        "title": "Кірпіш",
        "steps": [
            ("length", "1/4. Қабырға ұзындығы (м)?", _num(500)),
            ("height", "2/4. Қабырға биіктігі (м)?", _num(50)),
            ("opening", "3/4. Есік-терезе тесіктерінің ауданы (м²)? Жоқ болса 0 жазыңыз.",
             _num(1000, allow_zero=True)),
            ("thick", "4/4. Қалыңдығы: 0.5, 1, 1.5 немесе 2 кірпіш?",
             lambda t: parse_choice(t, list(BRICK_PER_M2))),
        ],
        "compute": calc_brick,
    },
    "tile": {
        "title": "Плитка",
        "steps": [
            ("length", "1/3. Бөлме ұзындығы (м)?", _num(200)),
            ("width", "2/3. Бөлме ені (м)?", _num(200)),
            ("tile", "3/3. Плитка өлшемі (см), мысалы 30x60?", parse_tile),
        ],
        "compute": calc_tile,
    },
    "paint": {
        "title": "Бояу",
        "steps": [
            ("area", "1/3. Боялатын аудан (м²)?", _num(10000)),
            ("coats", "2/3. Неше қабат (1-5)?",
             lambda t: parse_choice(t, [1, 2, 3, 4, 5])),
            ("cons", "3/3. Банкадағы шығын (м²/л), мысалы 10. Білмесеңіз 0 жазыңыз.",
             _num(100, allow_zero=True)),
        ],
        "compute": calc_paint,
    },
}

BUTTONS = {
    "🧱 Бетон": "concrete",
    "🧱 Кірпіш": "brick",
    "🔲 Плитка": "tile",
    "🎨 Бояу": "paint",
}

# ----------------------------------------------- диалог қозғалтқышы (таза)
STATE = {}  # chat_id -> {"calc": ..., "step": int, "data": {}}


def start_dialog(chat_id, calc_key):
    STATE[chat_id] = {"calc": calc_key, "step": 0, "data": {}}
    return CALCS[calc_key]["steps"][0][1] + "\n(Тоқтату: /cancel)"


def dialog_step(chat_id, text):
    """Белсенді диалогтың келесі қадамы. Жауап мәтінін қайтарады."""
    st = STATE[chat_id]
    calc = CALCS[st["calc"]]
    key, _, check = calc["steps"][st["step"]]
    value, err = check(text)
    if err:  # қате: сол сұрақты қайта қоямыз, диалог жалғасады
        return f"⚠️ {err}\n\n{calc['steps'][st['step']][1]}"
    st["data"][key] = value
    st["step"] += 1
    if st["step"] < len(calc["steps"]):
        return calc["steps"][st["step"]][1]
    result = calc["compute"](st["data"])
    del STATE[chat_id]
    if result is None:
        return "⚠️ Тесіктер ауданы қабырға ауданынан кем болуы керек. Қайта бастаңыз: /calc"
    return result + "\n\nҚайта есептеу: /calc"


def tip_of_day():
    return "💡 Бүгінгі кеңес:\n" + TIPS[datetime.date.today().toordinal() % len(TIPS)]


# ----------------------------------------------------------- Telegram бөлігі
def get_token():
    token = os.getenv("BOT_TOKEN")
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            token = os.getenv("BOT_TOKEN")
        except ImportError:
            pass
    if not token:
        try:
            from google.colab import userdata
            token = userdata.get("BOT_TOKEN")
        except Exception:
            pass
    if not token:
        raise SystemExit("BOT_TOKEN табылмады: жүйелік ортаға (Environment Variable) немесе .env файлына енгізіңіз.")
    return token


def main():
    import telebot
    from telebot import types

    bot = telebot.TeleBot(get_token())

    def main_menu():
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add("🧱 Бетон", "🧱 Кірпіш", "🔲 Плитка", "🎨 Бояу")
        kb.add("❓ Анықтамалық", "💡 Кеңес", "ℹ️ Көмек")
        return kb

    def calc_menu():
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(*[types.InlineKeyboardButton(c["title"], callback_data=f"calc:{k}")
                 for k, c in CALCS.items()])
        return kb

    def faq_menu():
        kb = types.InlineKeyboardMarkup(row_width=1)
        for i, (q, _) in enumerate(FAQ):
            kb.add(types.InlineKeyboardButton(f"{i + 1}. {q}", callback_data=f"faq:{i}"))
        return kb

    HELP = ("Командалар:\n"
            "/start - бастау\n/help - осы тізім\n"
            "/calc - материал есептеу (бетон, кірпіш, плитка, бояу)\n"
            "/tip - бүгінгі кеңес\n/faq - анықтамалық (10 сұрақ)\n"
            "/cancel - есептеуді тоқтату\n\n"
            "Төмендегі батырмалар да жұмыс істейді. Нәтиже шамамен есептеледі.")

    bot.set_my_commands([
        types.BotCommand("start", "Бастау"),
        types.BotCommand("help", "Командалар тізімі"),
        types.BotCommand("calc", "Материалдарды есептеу"),
        types.BotCommand("tip", "Бүгінгі кеңес"),
        types.BotCommand("faq", "Анықтамалық"),
        types.BotCommand("cancel", "Есептеуді тоқтату"),
    ])

    @bot.message_handler(commands=["start"])
    def on_start(m):
        STATE.pop(m.chat.id, None)
        bot.send_message(
            m.chat.id,
            "Сәлем! Мен құрылыс материалдарының калькуляторымын.\n"
            "Бетон, кірпіш, плитка және бояу көлемін есептеймін, "
            "қысқа анықтамалық пен кеңес беремін.\n\nБатырманы таңдаңыз немесе /help жазыңыз.",
            reply_markup=main_menu())

    @bot.message_handler(commands=["help"])
    def on_help(m):
        bot.send_message(m.chat.id, HELP, reply_markup=main_menu())

    @bot.message_handler(commands=["calc"])
    def on_calc(m):
        STATE.pop(m.chat.id, None)
        bot.send_message(m.chat.id, "Нені есептейміз?", reply_markup=calc_menu())

    @bot.message_handler(commands=["tip"])
    def on_tip(m):
        bot.send_message(m.chat.id, tip_of_day())

    @bot.message_handler(commands=["faq"])
    def on_faq(m):
        bot.send_message(m.chat.id, "Сұрақты таңдаңыз:", reply_markup=faq_menu())

    @bot.message_handler(commands=["cancel"])
    def on_cancel(m):
        if STATE.pop(m.chat.id, None):
            bot.send_message(m.chat.id, "Есептеу тоқтатылды. Жаңасын бастау: /calc",
                             reply_markup=main_menu())
        else:
            bot.send_message(m.chat.id, "Белсенді есептеу жоқ. Бастау: /calc")

    @bot.message_handler(func=lambda m: m.text and m.text.startswith("/"))
    def on_unknown_command(m):
        bot.send_message(m.chat.id, "Белгісіз команда. Тізім: /help")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("calc:"))
    def on_calc_button(c):
        bot.answer_callback_query(c.id)
        bot.send_message(c.message.chat.id, start_dialog(c.message.chat.id, c.data.split(":")[1]))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("faq:"))
    def on_faq_button(c):
        bot.answer_callback_query(c.id)
        q, a = FAQ[int(c.data.split(":")[1])]
        bot.send_message(c.message.chat.id, f"❓ {q}\n\n{a}")

    @bot.message_handler(content_types=["text"])
    def on_text(m):
        cid, text = m.chat.id, m.text.strip()
        if len(text) > MAX_TEXT:
            bot.send_message(cid, f"Хабарлама тым ұзын (ең көбі {MAX_TEXT} таңба). Қысқартып жіберіңіз.")
            return
        if text in BUTTONS:
            bot.send_message(cid, start_dialog(cid, BUTTONS[text]))
        elif text == "❓ Анықтамалық":
            on_faq(m)
        elif text == "💡 Кеңес":
            on_tip(m)
        elif text == "ℹ️ Көмек":
            on_help(m)
        elif cid in STATE:
            bot.send_message(cid, dialog_step(cid, text))
        else:
            bot.send_message(cid, "Түсінбедім. Батырманы таңдаңыз немесе /help жазыңыз.",
                             reply_markup=main_menu())

    @bot.message_handler(content_types=["photo", "sticker", "voice", "video", "audio",
                                        "document", "location", "contact", "animation",
                                        "video_note"])
    def on_non_text(m):
        bot.send_message(m.chat.id, "Мен тек мәтін қабылдаймын. Сан немесе команда жазыңыз: /help")

    print("Бот іске қосылды. Тоқтату: Ctrl+C")
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    main()
