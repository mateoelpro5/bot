import discord
from discord.ext import commands
import yt_dlp
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
import re
from collections import deque
from random import shuffle
import os

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")
print("SPOTIFY_CLIENT_ID:", SPOTIFY_CLIENT_ID)
print("SPOTIFY_CLIENT_SECRET:", SPOTIFY_CLIENT_SECRET)
print("GENIUS_TOKEN:", GENIUS_TOKEN)
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
))
genius = lyricsgenius.Genius(GENIUS_TOKEN)

queues = {}
now_playing = {}
volumes = {}
reaction_messages = {}
def is_spotify_url(url):
    return bool(re.match(r'https?://open.spotify.com/(track|episode)/', url))

def is_spotify_track(url):
    return re.match(r'https?://open\.spotify\.com/track/', url)

def is_spotify_playlist(url):
    return re.match(r'https?://open\.spotify\.com/playlist/', url)

def get_artist_and_title(spotify_url):
    if "episode" in spotify_url:
        episode_id = spotify_url.split("/")[-1].split("?")[0]
        info = sp.episode(episode_id)
        artist = info["show"]["publisher"]
        title = info["name"]
    else:
        track_id = spotify_url.split("/")[-1].split("?")[0]
        info = sp.track(track_id)
        artist = info["artists"][0]["name"]
        title = info["name"]
    return artist, title

def get_tracks_from_playlist(spotify_url):
    playlist_id = spotify_url.split('/')[-1].split('?')[0]
    results = sp.playlist_tracks(playlist_id)
    return [f"{item['track']['artists'][0]['name']} - {item['track']['name']}" for item in results['items']]

async def get_audio_url(search):
    def yt():
        opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch',
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            return info['url'], info['title']
    return await asyncio.to_thread(yt)

async def fetch_and_add(track, guild_id):
    try:
        url, title = await get_audio_url(track)
        queues[guild_id].append((url, title))
        return title
    except Exception as e:
        print(f"❌ Error agregando '{track}': {e}")
        return None

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def play_next(self, ctx, vc):
    guild_id = ctx.guild.id
    try:
        if queues.get(guild_id):
            url, title = queues[guild_id].popleft()
            now_playing[guild_id] = title

            source = discord.FFmpegPCMAudio(
                url, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn')
            volume = volumes.get(guild_id, 0.5)
            source = discord.PCMVolumeTransformer(source, volume)

            def after_play(error):
                if error:
                    print(f"❌ Error: {error}")
                fut = self.play_next(ctx, vc)
                asyncio.run_coroutine_threadsafe(fut, self.bot.loop)

            vc.play(source, after=after_play)

            if guild_id in reaction_messages:
                try:
                    asyncio.create_task(reaction_messages[guild_id].delete())
                except:
                    pass

            msg = await ctx.send(f"🎶 Reproduciendo: **{title}**\nReacciona para controlar:")
            for emoji in ["⏸️", "▶️", "⏭️", "⏹️", "🔉", "🔊"]:
                await msg.add_reaction(emoji)
            reaction_messages[guild_id] = msg
        else:
            await asyncio.sleep(5)
            if not queues.get(guild_id):
                now_playing[guild_id] = None
                if vc.is_connected():
                    await vc.disconnect()
                    await ctx.send("⏹️ Fin de la cola, desconectando.")
    except Exception as e:
        print(f"❌ Error en play_next: {e}")


    @commands.command()
    async def play(self, ctx, *, search: str):
        if not ctx.author.voice:
            return await ctx.send("🛑 Debes estar en un canal de voz.")

        voice_channel = ctx.author.voice.channel
        guild_id = ctx.guild.id

        if ctx.voice_client is None:
            vc = await voice_channel.connect()
        else:
            vc = ctx.voice_client
            if vc.channel != voice_channel:
                await vc.move_to(voice_channel)

        queues.setdefault(guild_id, deque())
        volumes.setdefault(guild_id, 0.5)

        if is_spotify_playlist(search):
            try:
                canciones = get_tracks_from_playlist(search)
                await ctx.send(f"📃 Playlist detectada. Añadiendo {len(canciones)} canciones...")
                added_titles = await asyncio.gather(
                    *[fetch_and_add(track, guild_id) for track in canciones]
                )
                total = len([t for t in added_titles if t])
                await ctx.send(f"✅ Se añadieron {total} canciones a la cola.")
            except Exception as e:
                return await ctx.send(f"❌ Error al procesar la playlist: {e}")
        elif is_spotify_track(search) or "episode" in search:
            try:
                artista, titulo = get_artist_and_title(search)
                search = f"{artista} - {titulo}"
                await ctx.send(f"🔎 Buscando en YouTube: **{search}**")
                url, title = await get_audio_url(search)
                queues[guild_id].append((url, title))
            except Exception as e:
                return await ctx.send(f"❌ Error con el link de Spotify: {e}")
        else:
            try:
                url, title = await get_audio_url(search)
                queues[guild_id].append((url, title))
            except Exception as e:
                return await ctx.send(f"❌ No se pudo obtener audio: {e}")

        await ctx.send(f"✅ Añadido a la cola: **{title}**")
        if not vc.is_playing() and not vc.is_paused():
            await self.play_next(ctx, vc)

    @commands.command()
    async def skip(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Saltado.")
        else:
            await ctx.send("⚠️ No hay música.")

    @commands.command()
    async def stop(self, ctx):
        vc = ctx.voice_client
        if vc:
            queues[ctx.guild.id] = deque()
            now_playing[ctx.guild.id] = None
            await vc.disconnect()
            await ctx.send("🛑 Bot detenido.")
        else:
            await ctx.send("❌ No estoy en voz.")

    @commands.command()
    async def pause(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send("⏸️ Pausado.")

    @commands.command()
    async def resume(self, ctx):
        vc = ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Reanudado.")

    @commands.command()
    async def shuffle(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in queues and queues[guild_id]:
            temp_list = list(queues[guild_id])
            shuffle(temp_list)
            queues[guild_id] = deque(temp_list)
            await ctx.send("🔀 Cola mezclada aleatoriamente.")
        else:
            await ctx.send("📭 No hay canciones en la cola para mezclar.")

    @commands.command()
    async def queue(self, ctx):
        q = queues.get(ctx.guild.id, deque())
        if not q:
            return await ctx.send("📭 La cola está vacía.")
        await ctx.send("🎶 Cola:\n" + "\n".join(f"{i+1}. {t}" for i, (_, t) in enumerate(q)))

    @commands.command()
    async def nowplaying(self, ctx):
        t = now_playing.get(ctx.guild.id)
        if t:
            await ctx.send(f"🎧 Ahora suena: **{t}**")
        else:
            await ctx.send("🎧 No suena nada.")

    @commands.command()
    async def lyrics(self, ctx, *, query: str = None):
        if query is None:
            query = now_playing.get(ctx.guild.id)
            if not query:
                return await ctx.send("🔇 No hay canción actual ni consulta dada.")
        await ctx.send(f"📄 Buscando letra: **{query}**")
        try:
            song = genius.search_song(query)
            if not song or not song.lyrics:
                return await ctx.send("❌ No encontré letra.")
            text = song.lyrics
            for i in range(0, len(text), 1900):
                await ctx.send(f"```{text[i:i+1900]}```")
        except Exception as e:
            await ctx.send(f"❌ Error buscando letra: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        msg = reaction.message
        ctx = await self.bot.get_context(msg)
        vc = ctx.voice_client
        gid = ctx.guild.id
        emoji = reaction.emoji

        if reaction_messages.get(gid) and msg.id == reaction_messages[gid].id:
            if emoji == "⏸️" and vc.is_playing():
                vc.pause()
            elif emoji == "▶️" and vc.is_paused():
                vc.resume()
            elif emoji == "⏭️":
                vc.stop()
            elif emoji == "⏹️":
                await vc.disconnect()
                queues[gid] = deque()
                now_playing[gid] = None
            elif emoji == "🔉":
                volumes[gid] = max(volumes[gid] - 0.1, 0.1)
            elif emoji == "🔊":
                volumes[gid] = min(volumes[gid] + 0.1, 2.0)
            await reaction.remove(user)

async def setup(bot):
    await bot.add_cog(Music(bot))
