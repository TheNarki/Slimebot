import os
import discord
from discord import app_commands
import random
from google.cloud import dialogflow_v2
from google.oauth2 import service_account
import json
from dotenv import load_dotenv
load_dotenv()

class BotDiscord(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

        # Configuration Dialogflow
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
        await self.tree.sync()

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

@client.event
async def on_ready():
    print("="*50)
    print(f"✅ Bot '{client.user}' connecté avec succès!")
    print(f"🔗 Connecté à {len(client.guilds)} serveurs")
    print(f"📝 Commandes slash disponibles avec /aide")
    print("="*50)
    await client.change_presence(activity=discord.Game(name="Tu peux Discuter avec moi! ou fait /aide"))
    client.start_time = discord.utils.utcnow()

CHANNEL_IDS = [
    759668011371462702,
    1275561641588691016,
]

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if CHANNEL_IDS and message.channel.id not in CHANNEL_IDS:
        return

    response = await client.detect_intent(message.content, str(message.author.id))
    if response:
        await message.channel.send(response)

@client.tree.command(name="aide", description="Affiche la liste des commandes disponibles")
async def aide(interaction: discord.Interaction):
    aide_texte = """
**Commandes disponibles:**
`/aide` - Affiche cette liste
`/des` - Lance un dé à 6 faces
`/pile_face` - Lance une pièce
`/info` - Informations sur le serveur
    """
    await interaction.response.send_message(aide_texte)

@client.tree.command(name="des", description="Lance un dé à 6 faces")
async def des(interaction: discord.Interaction):
    resultat = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 Le dé roule et... **{resultat}**!")

@client.tree.command(name="pile_face", description="Lance une pièce")
async def pile_face(interaction: discord.Interaction):
    resultat = random.choice(["Pile", "Face"])
    await interaction.response.send_message(f"La pièce tourne et... c'est **{resultat}**!")

@client.tree.command(name="info", description="Informations sur le serveur")
async def info(interaction: discord.Interaction):
    serveur = interaction.guild
    await interaction.response.send_message(f"""
**Informations sur le serveur:**
Nom: {serveur.name}
Nombre de membres: {serveur.member_count}
Créé le: {serveur.created_at.strftime('%d/%m/%Y')}
Propriétaire: {serveur.owner}
    """)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Erreur: DISCORD_BOT_TOKEN non défini dans les secrets")
    else:
        client.run(token)