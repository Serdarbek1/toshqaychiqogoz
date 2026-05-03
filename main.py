import asyncio
import random
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8745173491:AAHEEb7KZfCvJAoi4JKFSum7X03aefOP2fo"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===== STATE =====
queue = []
game_active = False
matches = {}
choices = {}

GROUP_ID = None

# ===== DATA =====
money = defaultdict(lambda: 100)
elo = defaultdict(lambda: 1000)
wins = defaultdict(int)
losses = defaultdict(int)
shield = defaultdict(int)   # 🛡 NEW

CHOICES = ["tosh", "qaychi", "qogoz"]

# ===== BUTTONS =====
def join_btn():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Qo‘shilish", callback_data="join")]
    ])

def rps_btn():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪨 Tosh", callback_data="tosh"),
            InlineKeyboardButton(text="✂️ Qaychi", callback_data="qaychi"),
            InlineKeyboardButton(text="📄 Qog‘oz", callback_data="qogoz"),
        ]
    ])

def shop_btn():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡 Shield (200💰)", callback_data="buy_shield")]
    ])

def name(u):
    return f"@{u.username}" if u.username else u.full_name


# ===== FIX CHAT MEMBER CLEAN NAME =====
async def clean_name(user_id):
    m = await bot.get_chat_member(GROUP_ID, user_id)
    u = m.user
    return f"@{u.username}" if u.username else u.full_name


# ===== WIN LOGIC =====
def win(a, b):
    if a == b:
        return 0
    if (a == "tosh" and b == "qaychi") or \
       (a == "qaychi" and b == "qogoz") or \
       (a == "qogoz" and b == "tosh"):
        return 1
    return -1


# ===== START =====
@dp.message(Command("start"))
async def start(message: types.Message):
    global GROUP_ID, game_active, queue

    GROUP_ID = message.chat.id
    game_active = False
    queue.clear()

    await message.answer(
        "🎮 Tosh Qaychi qog'oz\n\nQo‘shilish:",
        reply_markup=join_btn()
    )


# ===== SHOP =====
@dp.message(Command("shop"))
async def shop(message: types.Message):
    await message.answer("🏪 SHOP:", reply_markup=shop_btn())


@dp.callback_query(F.data == "buy_shield")
async def buy_shield(callback: types.CallbackQuery):
    u = callback.from_user.id

    if money[u] < 200:
        await callback.answer("❌ yetarli pul yo‘q")
        return

    money[u] -= 200
    shield[u] = 1   # 🛡 activate shield

    await callback.answer("🛡 Shield aktiv!")


# ===== JOIN =====
@dp.callback_query(F.data == "join")
async def join(callback: types.CallbackQuery):
    global game_active

    user = callback.from_user

    if game_active:
        await callback.answer("❌ o‘yin ketmoqda")
        return

    if user in queue:
        await callback.answer("⏳ allaqachon bor")
        return

    queue.append(user)
    await callback.answer("✅ qo‘shildingiz")

    await bot.send_message(GROUP_ID, f"➕ {name(user)} | 👥 {len(queue)}")

    if len(queue) >= 3 and not game_active:
        await start_game()


# ===== GAME START =====
async def start_game():
    global game_active

    game_active = True

    await bot.send_message(GROUP_ID, "⏳ 10 sekund start...")

    await asyncio.sleep(10)

    p1 = queue.pop(0)
    p2 = queue.pop(0)
    p3 = queue.pop(0)

    players = [p1, p2, p3]

    for p in players:
        matches[p.id] = [x.id for x in players if x.id != p.id]
        choices[p.id] = None

    await bot.send_message(
        GROUP_ID,
        f"⚔️ MATCH START\n\n{p1.full_name}\n{p2.full_name}\n{p3.full_name}",
        reply_markup=rps_btn()
    )

    await asyncio.sleep(8)

    for p in players:
        if choices[p.id] is None:
            choices[p.id] = random.choice(CHOICES)


# ===== ANALYZE =====
def analyze(players, results):
    vals = list(results.values())

    if len(set(vals)) == 3:
        return "restart", None, None

    count = defaultdict(list)
    for p, v in results.items():
        count[v].append(p)

    if len(count) == 2:
        g1, g2 = list(count.values())

        if len(g1) == 2:
            return "duel", g1, g2[0]
        else:
            return "duel", g2, g1[0]

    return "restart", None, None


# ===== PLAY =====
@dp.callback_query(F.data.in_(CHOICES))
async def play(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in matches:
        return

    choices[user_id] = callback.data
    await callback.answer("✔")

    players = [user_id] + matches[user_id]

    if all(choices.get(p) for p in players):

        results = {p: choices[p] for p in players}

        mode, duel_group, loser = analyze(players, results)

        text = "🏁 NATIJA\n\n"

        # CLEAN OUTPUT FIX 🔥
        for p in players:
            name_p = await clean_name(p)
            text += f"{name_p} → {results[p]}\n"

        # ===== RESTART =====
        if mode == "restart":
            text += "\n🔁 RANDOM CHAOS → RESTART"
            await bot.send_message(GROUP_ID, text)

            for p in players:
                matches.pop(p, None)
                choices.pop(p, None)

            queue.extend(players)

            await asyncio.sleep(3)
            await start_game()
            return

        # ===== DUEL =====
        p1, p2 = duel_group

        if win(results[p1], results[p2]) == 1:
            winner = p1
        else:
            winner = p2

        # 🛡 SHIELD CHECK
        for p in players:
            if p != winner:
                if shield[p]:
                    shield[p] = 0
                    text += f"\n🛡 {await clean_name(p)} shield blocked loss!"
                else:
                    losses[p] += 1
                    money[p] -= 30

        wins[winner] += 1
        money[winner] += 100
        elo[winner] += 25

        winner_name = await clean_name(winner)

        text += f"\n🏆 G‘olib: {winner_name}"

        await bot.send_message(GROUP_ID, text)

        for p in players:
            matches.pop(p, None)
            choices.pop(p, None)

        queue.extend(players)

        await asyncio.sleep(5)

        game_active = False


# ===== RUN =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())