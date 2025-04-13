import os
import discord
from discord.ext import commands
import random
from google.cloud import dialogflow_v2
from google.oauth2 import service_account
import json
from discord import FFmpegPCMAudio, PCMVolumeTransformer
import asyncio
from discord import app_commands  # Import app_commands pour utiliser les commandes slash
from dotenv import load_dotenv
import yt_dlp  
load_dotenv()

music_queues = {}
volume_levels = {}

intents = discord.Intents.default()
intents.message_content = True  # Si vous utilisez des messages pour commander le bot

bot = discord.Client(intents=intents)

class BotDiscord(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents, application_id=os.getenv("APPLICATION_ID"))

        try:
            credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not credentials_json:
                raise Exception("GOOGLE_APPLICATION_CREDENTIALS non défini")

            credentials_dict = json.loads(credentials_json)
            self.project_id = credentials_dict['project_id']

            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/dialogflow']
            )
            self.session_client = dialogflow_v2.SessionsClient(credentials=credentials)
            print("Dialogflow initialisé avec succès")
        except Exception as e:
            print(f"Erreur d'initialisation Dialogflow: {e}")
            self.session_client = None

    async def setup_hook(self):
        await self.tree.sync()  # Synchronise les commandes slash

    async def detect_intent(self, text, session_id):
        if not self.session_client:
            return "Désolé, je ne peux pas traiter les messages pour le moment."

        session = self.session_client.session_path(self.project_id, session_id)
        text_input = dialogflow_v2.TextInput(text=text, language_code="fr")
        query_input = dialogflow_v2.QueryInput(text=text_input)

        try:
            response = self.session_client.detect_intent(
                request={"session": session, "query_input": query_input}
            )
            return response.query_result.fulfillment_text
        except Exception as e:
            print(f"Erreur Dialogflow: {e}")
            return "Désolé, une erreur s'est produite."

client = BotDiscord()

target_channels = [759668011371462702, 1275561641588691016, 1275745333367935079]

@client.event
async def on_ready():
    print("="*50)
    print(f"✅ Bot '{client.user}' connecté avec succès!")
    print(f"🔗 Connecté à {len(client.guilds)} serveurs")
    print(f"📝 Commandes slash disponibles avec /aide")
    print("="*50)
    await client.change_presence(activity=discord.Game(name="Discute avec moi! Saluez-moi !"))

# Liste des URL de musique à jouer aléatoirement
MUSIC_LIST = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
    "https://www.youtube.com/watch?v=3JZ_D3ELwOQ",  # Pharrell Williams - Happy
    "https://www.youtube.com/watch?v=9bZkp7q19f0",  # PSY - Gangnam Style
    "https://www.youtube.com/watch?v=KQ6zr6kCPj8",  # Aqua - Barbie Girl
    "https://www.youtube.com/watch?v=2Vv-BfVoq4g"   # Ed Sheeran - Perfect
]

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if target_channels and message.channel.id not in target_channels:
        return
    
    # 10% de chance que de la musique soit jouée
    if random.random() < 0.1 and message.author.voice:
        # Si l'utilisateur est dans un salon vocal
        voice_channel = message.author.voice.channel
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        
        if not voice_client or not voice_client.is_connected():
            # Se connecter au canal vocal si pas déjà connecté
            voice_client = await voice_channel.connect()

        # Choisir une musique aléatoire dans la liste
        music_url = random.choice(MUSIC_LIST)
        music_queues.setdefault(message.guild.id, []).append((music_url, message))

        ydl_opts = {'format': 'bestaudio', 'quiet': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(music_url, download=False)
            audio_url = info['url']

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        volume = volume_levels.get(message.guild.id, 1.0)
        source = PCMVolumeTransformer(FFmpegPCMAudio(audio_url, **ffmpeg_options), volume)

        # Lancer la lecture
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(message.guild, voice_client), client.loop))
        await message.channel.send(f"🎶 Lecture : {info['title']}")
    else:
        # Si aucune musique n'est jouée, traite le message normalement
        response = await client.detect_intent(message.content, str(message.author.id))
        if response:
            await message.channel.send(response)

async def play_next(guild, voice_client):
    music_queues.setdefault(guild.id, [])
    if music_queues[guild.id]:
        await play_music_queue(guild, voice_client)
    else:
        await voice_client.disconnect()

async def play_music_queue(guild, voice_client):
    music_queues.setdefault(guild.id, [])
    if music_queues[guild.id]:
        url, interaction = music_queues[guild.id].pop(0)
        ydl_opts = {'format': 'bestaudio', 'quiet': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        volume = volume_levels.get(guild.id, 1.0)
        source = PCMVolumeTransformer(FFmpegPCMAudio(audio_url, **ffmpeg_options), volume)

        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild, voice_client), client.loop))
        await interaction.followup.send(f"🎶 Lecture : {info['title']}")
    else:
        await voice_client.disconnect()

# Commandes du bot

@client.tree.command(name="play", description="Joue une musique depuis YouTube")
@commands.guild_only()
@app_commands.describe(url="URL de la vidéo YouTube")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    
    # Vérifier si l'utilisateur est dans un salon vocal
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.followup.send("❌ Tu dois être dans un salon vocal.")
        return
    
    # Vérifier si le bot est déjà connecté à un salon vocal
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    
    if voice_client:  # Le bot est déjà connecté à un salon
        if voice_client.channel != voice_channel:
            # Si le bot est connecté à un autre salon, déconnectez-le d'abord
            await voice_client.disconnect()
            voice_client = await voice_channel.connect()  # Rejoindre le bon salon
        else:
            await interaction.followup.send(f"✅ Déjà connecté au salon vocal '{voice_channel.name}'.")
    else:
        # Le bot n'est pas encore connecté, il rejoint donc le salon vocal
        voice_client = await voice_channel.connect()
    
    # Ajouter la musique à la file d'attente et commencer à jouer
    music_queues.setdefault(interaction.guild.id, []).append((url, interaction))
    await interaction.followup.send(f"🎶 Ajouté à la file : {url}")
    
    # Si le bot ne joue pas déjà de la musique, commencez à jouer
    if not voice_client.is_playing():
        await play_music_queue(interaction.guild, voice_client)

@client.tree.command(name="pause", description="Met la musique en pause")
async def pause(interaction: discord.Interaction):
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Musique mise en pause.")
    else:
        await interaction.response.send_message("❌ Aucune musique en cours de lecture.")

@client.tree.command(name="resume", description="Reprend la musique")
async def resume(interaction: discord.Interaction):
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Musique reprise.")
    else:
        await interaction.response.send_message("❌ Aucune musique en pause.")

@client.tree.command(name="skip", description="Passe à la musique suivante")
async def skip(interaction: discord.Interaction):
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Musique sautée.")
    else:
        await interaction.response.send_message("❌ Aucune musique à passer.")

@client.tree.command(name="stop", description="Arrête la musique et quitte le salon")
async def stop(interaction: discord.Interaction):
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)
    music_queues[interaction.guild.id] = []
    if vc:
        await vc.disconnect()
    await interaction.response.send_message("🛑 Lecture arrêtée et file vidée.")

# Autres commandes...

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Erreur: DISCORD_BOT_TOKEN non défini")
    else:
        client.run(token)