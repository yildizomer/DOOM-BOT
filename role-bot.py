import discord
from discord.ext import commands

# -------------- Ayarlar -----------------
# -------------- Settings -----------------
TOKEN = "" # Bot tokeninizi buraya girin
# Enter your bot token here

GUILD_ID = 1111111111111111111 # Sunucu ID'sini buraya girin
# Enter your server (guild) ID here
MALE_ROLE_ID = 1111111111111111111 # Erkek rolü ID'sini buraya girin
# Enter the male role ID here
FEMALE_ROLE_ID = 1111111111111111111 # Kadın rolü ID'sini buraya girin
# Enter the female role ID here
ROLE_CHANNEL_ID = 1111111111111111111 # Rol mesajının gönderileceği kanal ID'sini buraya girin
# Enter the channel ID where the role message will be sent
VOICE_CHANNEL_ID = 1111111111111111111 # Botun bağlanacağı ses kanalının ID'sini buraya girin
# Enter the voice channel ID the bot will connect to

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------- Butonlar -----------------
# -------------- Buttons -----------------
class GenderRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Süresiz aktif
        # Active indefinitely

    @discord.ui.button(label="Erkek", style=discord.ButtonStyle.primary, custom_id="role_male")
    async def male_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = bot.get_guild(GUILD_ID)
        role = guild.get_role(MALE_ROLE_ID)
        member = interaction.user

        if role in member.roles:
            await interaction.response.send_message("Zaten Erkek rolüne sahipsin.", ephemeral=True)
            return

        await member.add_roles(role)
        # Kadın rolü varsa kaldır
        # Remove female role if present
        female_role = guild.get_role(FEMALE_ROLE_ID)
        if female_role in member.roles:
            await member.remove_roles(female_role)
        await interaction.response.send_message("Erkek rolü verildi!", ephemeral=True)

    @discord.ui.button(label="Kadın", style=discord.ButtonStyle.danger, custom_id="role_female")
    async def female_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = bot.get_guild(GUILD_ID)
        role = guild.get_role(FEMALE_ROLE_ID)
        member = interaction.user

        if role in member.roles:
            await interaction.response.send_message("Zaten Kadın rolüne sahipsin.", ephemeral=True)
            return

        await member.add_roles(role)
        # Erkek rolü varsa kaldır
        # Remove male role if present
        male_role = guild.get_role(MALE_ROLE_ID)
        if male_role in member.roles:
            await member.remove_roles(male_role)
        await interaction.response.send_message("Kadın rolü verildi!", ephemeral=True)

# -------------- Mesajı Gönderme -----------------
# -------------- Sending the Message -----------------
async def send_role_message():
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(ROLE_CHANNEL_ID)

    embed = discord.Embed(
        title="Selamlar, K U R S U N üyeleri! 🦇",
        description=(
            "🤡 Troll, sanal mafyalık, yanlış cinsiyet rolü seçimi yapmaya çalışanlar kalıcı ban yer.\n\n"
            "**Kayıt olmak için alttaki butonlardan cinsiyetinizi seçmeniz yeterlidir.**"
        ),
        color=discord.Color.blue()
    )

    # Önceki rol mesajlarını sil (isteğe bağlı)
    # Delete previous role messages (optional)
    async for msg in channel.history(limit=100):
        if msg.author == bot.user and msg.embeds:
            await msg.delete()

    await channel.send(embed=embed, view=GenderRoleView())

# -------------- Bot Eventleri -----------------
# -------------- Bot Events -----------------
@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı!")
    await send_role_message()

    # Ses kanalına bağlan
    # Connect to voice channel
    guild = bot.get_guild(GUILD_ID)
    voice_channel = guild.get_channel(VOICE_CHANNEL_ID)
    if voice_channel and isinstance(voice_channel, discord.VoiceChannel):
        if not guild.voice_client:
            await voice_channel.connect()
            print(f"{bot.user} sessiz ses kanalında bekliyor.")
        else:
            print("Bot zaten ses kanalına bağlı.")

# -------------- Botu Çalıştır -----------------
# -------------- Run the Bot -----------------
bot.run(TOKEN)
