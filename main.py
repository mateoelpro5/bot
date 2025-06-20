import discord
from discord.ext import commands
import os
import discord.opus

if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus('libopus.so')
        print("✅ Opus cargado correctamente.")
    except Exception as e:
        print(f"❌ No se pudo cargar Opus: {e}")
        
TOKEN = os.getenv("DISCORD_TOKEN")
print("TOKEN:", TOKEN)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Conectado como {bot.user}")

async def main():
    try:
        await bot.load_extension("music")
        print("🎵 Módulo de música cargado correctamente.")
    except Exception as e:
        print(f"❌ Error al cargar el módulo: {e}")
    
    await bot.start(TOKEN)


# Ejecutar el bot
if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
