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
from flask import Flask
import threading
from datetime import datetime, time

# Flask app pour garder le bot réveillé
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord actif !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()
load_dotenv()

# Récupère le chemin absolu du dossier où se trouve le script Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Crée un chemin vers le dossier sounds
sound_file = os.path.join(BASE_DIR, "sounds", "poisson.mp3", "Rick.mp3")
                          
# Ajoutez cette ligne pour définir les options FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Chemin vers le dossier des sons
SOUNDS_FOLDER = os.path.join(BASE_DIR, "sounds")

# Définition de la fonction get_sound_path
def get_sound_path(filename):
    return os.path.join(SOUNDS_FOLDER, filename)

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

    #On message

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Vérifie si le message est dans les salons cibles
    if target_channels and message.channel.id not in target_channels:
        return

    # Mots-clés spéciaux qui jouent un son
    keyword_actions = {
        "poisson": {
            "sound": "poisson.mp3",
        },
        "steve": {
            "sound": "Steve.mp3",
        },
        "zizi": {
            "sound": "zizi.mp3",
        },
        "caca": {
            "sound": "caca.mp3",
        },
        "Rick": {
            "sound": "Rick.mp3",
        },
        "AAAAAAAA": {
            "sound": "Screamer.mp3",
        },
        "aaaaaaaa": {
            "sound": "Screamer.mp3",
        },
        "darwin": {
            "sound": "Darwin.mp3",
        },
        "chemin": {
            "sound": "Darwin.mp3",
        }
        # Ajoute d'autres mots ici si besoin
    }

    # Réagit au premier mot-clé détecté seulement
    for keyword, action in keyword_actions.items():
        if keyword in message.content.lower():
            if message.author.voice and message.author.voice.channel:
                voice_channel = message.author.voice.channel
                vc = message.guild.voice_client
                if not vc or not vc.is_connected():
                    vc = await voice_channel.connect()
                elif vc.channel != voice_channel:
                    await vc.move_to(voice_channel)

                sound_path = os.path.join(BASE_DIR, "sounds", action["sound"])
                if os.path.exists(sound_path):
                    if vc.is_playing():
                        vc.stop()

                    def after_play(e):
                        coro = vc.disconnect()
                        fut = asyncio.run_coroutine_threadsafe(coro, client.loop)
                        try:
                            fut.result()
                        except Exception as e:
                            print(f"Erreur lors de la déconnexion : {e}")

                    vc.play(discord.FFmpegPCMAudio(sound_path), after=after_play)
                else:
                    await message.channel.send(f"🔇 Fichier introuvable : `{action['sound']}`")
            break  # On arrête dès qu'un mot-clé a été trouvé et traité

    # Réaction à "ta gueule"
    if "ta gueule" in message.content.lower():
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client and voice_client.is_connected():
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            music_queues[message.guild.id] = []
            await message.channel.send("D'accord 😢")
        else:
            await message.channel.send("Hein ? Je disais rien moi 😶")
        return

    # Traitement par Dialogflow
    response = await client.detect_intent(message.content, str(message.author.id))
    if response:
        await message.channel.send(response)

    # Nécessaire pour les slash commands
    await client.process_commands(message)

# Commandes du bot
@client.tree.command(name="joue", description="Joue une musique locale depuis le dossier /sounds")
@app_commands.describe(fichier="Nom du fichier (ex: Rick.mp3)")
async def joue(interaction: discord.Interaction, fichier: str):
    await interaction.response.defer()

    # Vérification du fichier
    file_path = os.path.join(SOUNDS_FOLDER, fichier)
    if not os.path.isfile(file_path):
        await interaction.followup.send(f"❌ Le fichier `{fichier}` n'existe pas dans `/sounds`.")
        return

    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ Tu dois être connecté à un salon vocal.")
        return

    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.followup.send("❌ Tu dois être connecté à un salon vocal.")
        return

    # Connexion
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if not voice_client or not voice_client.is_connected():
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    # Jouer le fichier
    try:
        if voice_client.is_playing():
            voice_client.stop()

        voice_client.play(
            FFmpegPCMAudio(file_path),
            after=lambda e: print(f"[DEBUG] Lecture terminée : {e}")
        )

        await interaction.followup.send(f"🎧 Lecture : `{fichier}`")

        # Attendre que la musique se termine
        while voice_client.is_playing():
            await asyncio.sleep(1)

        await voice_client.disconnect()
        print(f"[DEBUG] Déconnecté de {voice_channel.name}")

    except Exception as e:
        print(f"Erreur : {e}")  # Log interne
        await interaction.followup.send("❌ Une erreur est survenue.")

@client.tree.command(name="liste", description="Affiche la liste des musiques locales disponibles dans /sounds")
async def liste(interaction: discord.Interaction):
    await interaction.response.defer()

    # Répertoire des sons locaux
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SOUNDS_FOLDER = os.path.join(BASE_DIR, "sounds")

    try:
        files = [f for f in os.listdir(SOUNDS_FOLDER) if f.endswith('.mp3')]
        if not files:
            await interaction.followup.send("📁 Aucun fichier .mp3 trouvé dans `/sounds`.")
            return

        message = "**🎵 Liste des musiques dispo :**\n"
        message += "\n".join(f"- `{file}`" for file in files)

        await interaction.followup.send(message)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la lecture du dossier : {e}")

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

@client.tree.command(name="skip", description="Passe à la musique suivante.")
@commands.guild_only()
async def skip(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        guild_id = interaction.guild.id
        queue = music_queues.get(guild_id, [])

        voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)

        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("❌ Je ne suis pas connecté à un salon vocal.")
            return

        if not queue:
            await interaction.followup.send("❌ Aucune musique à passer.")
            return

        # Arrête la musique actuelle
        if voice_client.is_playing():
            voice_client.stop()
            await interaction.followup.send("⏭️ Musique passée.")
        else:
            await interaction.followup.send("❌ Je ne joue rien actuellement.")
    except Exception as e:
        print(f"Erreur : {e}")  # Log interne
        await interaction.followup.send("❌ Une erreur est survenue.")

@client.tree.command(name="stop", description="Arrête la musique et vide la file.")
@commands.guild_only()
async def stop(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        guild_id = interaction.guild.id
        voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)

        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("❌ Je ne suis pas connecté à un salon vocal.")
            return

        if voice_client.is_playing():
            voice_client.stop()

        # Déconnexion et nettoyage
        await voice_client.disconnect()
        music_queues[guild_id] = []
        await interaction.followup.send("⏹️ Musique arrêtée et file vidée.")
    except Exception as e:
        print(f"Erreur : {e}")  # Log interne
        await interaction.followup.send("❌ Une erreur est survenue.")

@client.tree.command(name="play", description="Joue une vidéo YouTube dans un salon vocal.")
@app_commands.describe(url="URL de la vidéo YouTube")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()

    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ Tu dois être connecté à un salon vocal.")
        return

    voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)

    # Connexion au salon vocal
    if not voice_client or not voice_client.is_connected():
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    # Télécharger l'audio avec yt_dlp
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': False,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']
            title = info.get('title', 'Audio')

        # Jouer l'audio
        if voice_client.is_playing():
            voice_client.stop()

        voice_client.play(
            FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS),
            after=lambda e: print(f"[DEBUG] Lecture terminée : {e}")
        )

        await interaction.followup.send(f"🎶 Lecture : **{title}**")
    except Exception as e:
        print(f"Erreur : {e}")  # Log interne
        await interaction.followup.send("❌ Une erreur est survenue lors de la lecture de la vidéo.")

# Autres commandes...

if __name__ == "__main__":
    keep_alive()  # <--- active le mini serveur web
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Erreur: DISCORD_BOT_TOKEN non défini")
    else:
        client.run(token)