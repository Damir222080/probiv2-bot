import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect('cache.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS cache
             (query TEXT PRIMARY KEY, result TEXT, timestamp TEXT)''')
conn.commit()

def get_cache(query):
    c.execute('SELECT result, timestamp FROM cache WHERE query=?', (query,))
    row = c.fetchone()
    if row:
        ts = datetime.fromisoformat(row[1])
        if datetime.now() - ts < timedelta(hours=24):
            return row[0]
    return None

def set_cache(query, result):
    c.execute('REPLACE INTO cache VALUES (?, ?, ?)',
              (query, result, datetime.now().isoformat()))
    conn.commit()

async def phone_lookup(phone):
    async with aiohttp.ClientSession() as session:
        url = f"http://ip-api.com/json/{phone}?fields=status,country,regionName,city,isp,org,timezone"
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get('status') == 'success':
                return (f"📱 Номер: {phone}\n"
                        f"Страна: {data.get('country', '—')}\n"
                        f"Регион: {data.get('regionName', '—')}\n"
                        f"Город: {data.get('city', '—')}\n"
                        f"Провайдер: {data.get('isp', '—')}\n"
                        f"Организация: {data.get('org', '—')}")
            else:
                url2 = f"https://api.veriphone.io/v2/verify?phone={phone}&default_country=RU"
                async with session.get(url2) as resp2:
                    data2 = await resp2.json()
                    if data2.get('status') == 'success':
                        return (f"📱 Номер: {phone}\n"
                                f"Страна: {data2.get('country_code', '—')}\n"
                                f"Оператор: {data2.get('carrier', '—')}\n"
                                f"Тип: {data2.get('phone_type', '—')}")
                    return "❌ Данные не найдены"

async def name_lookup(name):
    async with aiohttp.ClientSession() as session:
        url = f"https://html.duckduckgo.com/html/?q={name}"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            results = soup.find_all('a', class_='result__a')[:5]
            if results:
                lines = []
                for r in results:
                    title = r.get_text(strip=True)
                    link = r.get('href', '')
                    if link.startswith('/'):
                        link = 'https://duckduckgo.com' + link
                    lines.append(f"• {title} – {link}")
                return "🔍 Найдено:\n" + "\n".join(lines)
            return "❌ Ничего не найдено"

async def email_lookup(email):
    async with aiohttp.ClientSession() as session:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        async with session.get(url) as resp:
            if resp.status == 200:
                breaches = await resp.json()
                return f"⚠️ Утечки: {', '.join([b['Name'] for b in breaches])}"
    return "✅ Безопасно (утечек не найдено)"

async def ip_lookup(ip):
    async with aiohttp.ClientSession() as session:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org,timezone"
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get('status') == 'success':
                return (f"🌍 IP: {ip}\n"
                        f"Страна: {data.get('country', '—')}\n"
                        f"Регион: {data.get('regionName', '—')}\n"
                        f"Город: {data.get('city', '—')}\n"
                        f"Провайдер: {data.get('isp', '—')}\n"
                        f"Организация: {data.get('org', '—')}")
            return "❌ IP не определён"

@dp.message(Command('start'))
async def start(msg: Message):
    await msg.answer(
        "🧠 Бот-пробив (агрегатор публичных данных)\n"
        "Команды:\n"
        "/phone 79991234567\n"
        "/name Иван Иванов\n"
        "/email test@mail.ru\n"
        "/ip 8.8.8.8\n"
        "/help — список команд"
    )

@dp.message(Command('help'))
async def help_cmd(msg: Message):
    await msg.answer("Все команды: /start, /phone, /name, /email, /ip")

@dp.message()
async def handle(msg: Message):
    text = msg.text
    if not text:
        return
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return
    cmd, query = parts[0], parts[1].strip()
    cached = get_cache(query)
    if cached:
        await msg.answer(f"📦 (кеш)\n{cached}")
        return
    if cmd == '/phone':
        res = await phone_lookup(query)
    elif cmd == '/name':
        res = await name_lookup(query)
    elif cmd == '/email':
        res = await email_lookup(query)
    elif cmd == '/ip':
        res = await ip_lookup(query)
    else:
        await msg.answer("Неизвестная команда. Используй /help")
        return
    set_cache(query, res)
    await msg.answer(res)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
