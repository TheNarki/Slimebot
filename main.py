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

# Récupère le chemin absolu du dossier où se trouve le script Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Crée un chemin vers le dossier sounds
sound_file = os.path.join(BASE_DIR, "sounds", "poisson.mp3", "Rick.mp3")
                          
# Ajoutez cette ligne pour définir les options FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

SOUNDS_FOLDER = os.path.join(BASE_DIR, "sounds")

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

# Liste des fichiers audio
MUSIC_LIST = [
    "Rick.mp3",      # Rick Astley
    "poisson.mp3",   # Poisson steve
]

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Vérifie si le message est dans les salons cibles
    if target_channels and message.channel.id not in target_channels:
        return

    # Gestion des mots-clés "poisson" ou "steve"
    if "poisson" in message.content.lower() or "steve" in message.content.lower():
        if message.author.voice and message.author.voice.channel:
            voice_channel = message.author.voice.channel
            try:
                # Connecte le bot si nécessaire
                if not message.guild.voice_client:
                    vc = await voice_channel.connect()
                else:
                    vc = message.guild.voice_client

                # Choix du son en fonction du mot-clé
                if "poisson" in message.content.lower():
                    sound_file = get_sound_path("poisson.mp3")
                elif "steve" in message.content.lower():
                    sound_file = get_sound_path("Rick.mp3")

                # Stop l'audio en cours et joue le nouveau son
                vc.stop()
                vc.play(FFmpegPCMAudio(sound_file), after=lambda e: print("Lecture terminée."))

                await message.channel.send(f"🎵 Son lancé : {os.path.basename(sound_file)}")

                # Déconnexion après la lecture
                while vc.is_playing():
                    await asyncio.sleep(1)  # Attend que la lecture soit finie
                await vc.disconnect()

            except Exception as e:
                await message.channel.send(f"Erreur : {e}")
        else:
            await message.channel.send("❌ Tu dois être dans un salon vocal pour que je joue le son !")

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
        try:
            await interaction.followup.send(f"🎶 Lecture : {info['title']}")
        except discord.errors.InteractionResponded:
            print("L'interaction a expiré, impossible d'envoyer un message.")
    else:
        await voice_client.disconnect()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Chemin vers le dossier des musiques locales
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SOUNDS_FOLDER = os.path.join(BASE_DIR, "sounds")

    # Vérifie que l'auteur est connecté à un salon vocal
    if message.author.voice and message.author.voice.channel:
        chance = random.random()
        print(f"💡 Chance: {chance}")  # Debug

        if chance < 0.5:  # 50% pour tester (change à 0.1 après test !)
            try:
                files = [f for f in os.listdir(SOUNDS_FOLDER) if f.endswith('.mp3')]
                if files:
                    selected_file = random.choice(files)
                    sound_file = os.path.join(SOUNDS_FOLDER, selected_file)

                    voice_channel = message.author.voice.channel
                    voice_client = discord.utils.get(client.voice_clients, guild=message.guild)

                    if not voice_client or not voice_client.is_connected():
                        voice_client = await voice_channel.connect()
                        print(f"🔊 Connecté au salon : {voice_channel.name}")
                    elif voice_client.channel != voice_channel:
                        await voice_client.disconnect()
                        voice_client = await voice_channel.connect()
                        print(f"🔁 Déplacé au salon : {voice_channel.name}")

                    if voice_client.is_playing():
                        voice_client.stop()

                    def after_play(e):
                        coro = voice_client.disconnect()
                        fut = asyncio.run_coroutine_threadsafe(coro, client.loop)
                        try:
                            fut.result()
                            print("📤 Déconnecté après lecture.")
                        except Exception as e:
                            print(f"Erreur lors de la déconnexion : {e}")

                    voice_client.play(FFmpegPCMAudio(sound_file), after=after_play)
                    await message.channel.send(f"🎵 Surprise musicale : `{selected_file}`")
                else:
                    await message.channel.send("📂 Aucun fichier .mp3 trouvé dans `/sounds`.")
            except Exception as e:
                await message.channel.send(f"❌ Erreur : {e}")
                print(f"Erreur détaillée : {e}")
        else:
            print("💤 Pas de musique cette fois.")

    # Et enfin : le traitement Dialogflow
    response = await client.detect_intent(message.content, str(message.author.id))
    if response:
        await message.channel.send(response)

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
        await interaction.followup.send(f"❌ Erreur : {e}")

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

@client.tree.command(name="skip", description="Passe à la musique suivante")
async def skip(interaction: discord.Interaction):
    vc = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Musique sautée.")
    else:
        await interaction.response.send_message("❌ Aucune musique à passer.")

def get_sound_path(filename):
    return os.path.join(SOUNDS_FOLDER, filename)

# Autres commandes...

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Erreur: DISCORD_BOT_TOKEN non défini")
    else:
        client.run(token)