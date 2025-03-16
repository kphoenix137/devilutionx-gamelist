import discord
import asyncio
import threading
import os  # <-- Import os to access environment variables
from discord.ext import commands
from flask import Flask
from game_manager import refresh_game_list
from commands import setup_commands
from utils import load_config
from typing import Dict, Any

# Setup Discord Bot
intents = discord.Intents.default()
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready() -> None:
    print(f"✅ Logged in as {client.user}")
    await setup_commands(client)
    client.loop.create_task(background_task())

async def background_task() -> None:
    """Periodically refreshes the game list with dynamically loaded config."""
    while True:
        await refresh_game_list(client, load_config())
        await asyncio.sleep(load_config()["refresh_time"])

# Flask Web Server (Keeps Cloud Run from shutting down)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!", 200

# Run Discord Bot in a Separate Thread
def run_bot():
    token = os.getenv("DISCORD_BOT_TOKEN")  # <-- Read token from an environment variable
    if not token:
        raise ValueError("❌ DISCORD_BOT_TOKEN is not set!")
    client.run(token)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()  # Start bot in background
    app.run(host="0.0.0.0", port=8080)  # Keeps Cloud Run happy
