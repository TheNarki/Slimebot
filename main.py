
import os
import discord
from discord import app_commands
import random
from google.cloud import dialogflow
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

class BotDiscord(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_json:
            import json
            credentials_dict = json.loads(credentials_json)
            self.project_id = credentials_dict['project_id']
            
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            self.session_client = dialogflow.SessionsClient(credentials=credentials)
        else:
            raise Exception("GOOGLE_APPLICATION_CREDENTIALS non défini dans les secrets")

    async def setup_hook(self):
        await self.tree.sync()

    async def detect_intent(self, text, session_id):
        session = self.session_client.session_path(self.project_id, session_id)
        text_input = dialogflow.TextInput(text=text, language_code="fr")
        query_input = dialogflow.QueryInput(text=text_input)
        
        try:
            response = self.session_client.detect_intent(
                request={"session": session, "query_input": query_input}
            )
            return response.query_result.fulfillment_text
        except Exception as e:
            print(f"Erreur Dialogflow: {e}")
            return None

client = BotDiscord()

@client.event
async def on_ready():
    print(f'Bot connecté en tant que {client.user}')
    await client.change_presence(activity=discord.Game(name="/aide pour les commandes"))
    client.start_time = discord.utils.utcnow()

CHANNEL_IDS = [
    759668011371462702, 
    1275561641588691016,
    
    # Premier canal
    # Ajoutez d'autres IDs de canaux ici, par exemple:
    # 123456789,
    # 987654321,
]

@client.event
async def on_message(message):
    if message.author == client.user:
        return
        
    # Vérifie si le message est dans un des canaux autorisés
    if CHANNEL_IDS and message.channel.id not in CHANNEL_IDS:
        return

    # Traite le message avec Dialogflow
    response = await client.detect_intent(message.content, str(message.author.id))
    if response:
        await message.channel.send(response)

@client.tree.command(name="aide", description="Affiche la liste des commandes disponibles")
async def aide(interaction: discord.Interaction):
    aide_texte = """
**Commandes disponibles:**
`/aide` - Affiche cette liste
`/bonjour` - Le bot vous dit bonjour
`/des` - Lance un dé à 6 faces
`/pile_face` - Lance une pièce
`/info` - Informations sur le serveur
`!chat [message]` - Discuter avec l'IA
    """
    await interaction.response.send_message(aide_texte)

@client.tree.command(name="bonjour", description="Le bot vous dit bonjour")
async def bonjour(interaction: discord.Interaction):
    messages = [
        f"Salut {interaction.user.mention}! Comment ça va?",
        f"Bonjour {interaction.user.mention}! Ravi de te voir!",
        f"Coucou {interaction.user.mention}! Passe une bonne journée!"
    ]
    await interaction.response.send_message(random.choice(messages))

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

@client.tree.command(name="spam", description="Envoie un message plusieurs fois dans un canal avec intervalle aléatoire")
async def spam(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    repetitions: int,
    intervalle_min: int,
    intervalle_max: int
):
    if repetitions > 20:
        await interaction.response.send_message("Le nombre maximum de répétitions est de 20.", ephemeral=True)
        return
    
    if intervalle_min < 1 or intervalle_max < 1:
        await interaction.response.send_message("L'intervalle minimum est de 1 seconde.", ephemeral=True)
        return

    if intervalle_min > intervalle_max:
        await interaction.response.send_message("L'intervalle minimum doit être inférieur à l'intervalle maximum.", ephemeral=True)
        return
        
    await interaction.response.send_message(f"Je vais envoyer '{message}' {repetitions} fois dans {channel.mention} avec un intervalle aléatoire entre {intervalle_min} et {intervalle_max} secondes.", ephemeral=True)
    
    import asyncio
    for i in range(repetitions):
        await channel.send(message)
        intervalle = random.randint(intervalle_min, intervalle_max)
        await asyncio.sleep(intervalle)

@client.tree.command(name="uptime", description="Affiche depuis combien de temps le bot est en ligne")
async def uptime(interaction: discord.Interaction):
    now = discord.utils.utcnow()
    delta = now - client.start_time
    
    jours = delta.days
    heures = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    secondes = delta.seconds % 60
    
    message = f"Je suis en ligne depuis "
    if jours > 0:
        message += f"{jours} jours, "
    message += f"{heures:02d}:{minutes:02d}:{secondes:02d}"
    
    await interaction.response.send_message(message)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Erreur: DISCORD_BOT_TOKEN non défini dans les secrets")
    else:
        client.run(token)
