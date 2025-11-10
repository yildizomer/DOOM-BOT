# ...existing code...
# DOOM CUSTOM VOICE CHANNEL BOT

import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Kanal ve sunucu ID’leri / EN: Channel and server IDs
JOIN_TO_CREATE_CHANNEL_ID = 1111111111111111111  # Özel oda oluşturma kanalı ID / EN: ID of the channel to join to create a room
LOG_CHANNEL_ID =  1111111111111111111           # Log kanalı ID / EN: Log channel ID
WAIT_CHANNEL_ID =  1111111111111111111        # Botun bekleyeceği ses kanalı ID / EN: Voice channel ID where the bot will wait
GUILD_ID =  1111111111111111111            # Sunucu ID / EN: Guild (server) ID
DEFAULT_CAPACITY = 5

private_channels = {}  # {channel_id: {"owner_id": id, "message": interaction_message}} / EN: mapping of private channels

# Log fonksiyonu / EN: Log function
async def log_action(guild: discord.Guild, message: str, color: discord.Color = discord.Color.blurple()):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(description=message, color=color)
        await log_channel.send(embed=embed)

# Kullanıcı seçimi modal / EN: User selection modal
class MentionUserModal(Modal):
    def __init__(self, title, action, channel_id):
        super().__init__(title=title)
        self.action = action
        self.channel_id = channel_id
        self.user_input = TextInput(label="Kullanıcı adı veya ID gir", placeholder="Ahmet veya 123456789", required=True)
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        user_str = self.user_input.value.strip()
        user = None

        # Mention formatı / EN: Mention format
        if user_str.startswith("<@") and user_str.endswith(">"):
            try:
                user_id = int(user_str.replace("<@", "").replace("!", "").replace(">", ""))
                user = interaction.guild.get_member(user_id) or await interaction.guild.fetch_member(user_id)
            except:
                user = None
        # ID girilmiş olabilir / EN: Could be an ID
        elif user_str.isdigit():
            try:
                user_id = int(user_str)
                user = interaction.guild.get_member(user_id) or await interaction.guild.fetch_member(user_id)
            except:
                user = None
        # Kullanıcı adı ile dene / EN: Try by username
        else:
            user = discord.utils.get(interaction.guild.members, name=user_str)
            if not user:
                user = discord.utils.get(interaction.guild.members, display_name=user_str)

        if not user:
            await interaction.response.send_message("⚠️ Kullanıcı bulunamadı.", ephemeral=True)
            return

        try:
            if self.action == "allow":
                await channel.set_permissions(user, connect=True)
                await log_action(interaction.guild, f"🟢 {interaction.user.display_name} {user.display_name}’a giriş izni verdi")
                await interaction.response.send_message(f"✅ {user.display_name} artık odaya girebilir.", ephemeral=True)
            elif self.action == "ban":
                await channel.set_permissions(user, connect=False)
                if user.voice and user.voice.channel == channel:
                    await user.move_to(None)
                await log_action(interaction.guild, f"🔴 {interaction.user.display_name} {user.display_name}’ı odadan yasakladı")
                await interaction.response.send_message(f"🚫 {user.display_name} artık odaya giremez.", ephemeral=True)
            await update_panel(channel)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Bir hata oluştu: {e}", ephemeral=True)

# Kapasite modal / EN: Capacity modal
class LimitModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Oda Kapasitesini Ayarla")
        self.channel_id = channel_id
        self.limit_input = TextInput(label="Yeni kapasite (0 = sınırsız)", placeholder="5", required=True)
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            new_limit = int(self.limit_input.value)
            if new_limit < 0 or new_limit > 99:
                raise ValueError
            await channel.edit(user_limit=new_limit)
            await log_action(interaction.guild, f"🔧 {interaction.user.display_name} odanın kapasitesini {new_limit} olarak ayarladı")
            await interaction.response.send_message(f"✅ Oda kapasitesi {new_limit} olarak güncellendi.", ephemeral=True)
            await update_panel(channel)
        except ValueError:
            await interaction.response.send_message("⚠️ Geçerli bir sayı girin (0-99).", ephemeral=True)

# Oda ismi değiştirme modalı / EN: Channel rename modal
class RenameChannelModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Oda Adını Değiştir")
        self.channel_id = channel_id
        self.name_input = TextInput(label="Yeni oda adı", placeholder="Yeni Oda Adı", required=True)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        new_name = self.name_input.value.strip()
        try:
            await channel.edit(name=new_name)
            await log_action(interaction.guild, f"✏️ {interaction.user.display_name} odanın adını {new_name} olarak değiştirdi")
            await interaction.response.send_message(f"✅ Oda adı {new_name} olarak güncellendi.", ephemeral=True)
            await update_panel(channel)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Oda adı değiştirilemedi: {e}", ephemeral=True)

# Yönetim paneli / EN: Management panel
class ManageRoomView(View):
    def __init__(self, owner_id, channel_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.channel_id = channel_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Bu panel size ait değil.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Odaya girişleri aç", style=discord.ButtonStyle.success)
    async def open_room(self, interaction: discord.Interaction, button: Button):
        channel = interaction.guild.get_channel(self.channel_id)
        await channel.set_permissions(interaction.guild.default_role, connect=True)
        await log_action(interaction.guild, f"✅ {interaction.user.display_name} odaya girişleri açtı", color=discord.Color.green())
        await interaction.response.send_message("✅ Odaya girişler açıldı.", ephemeral=True)
        await update_panel(channel)

    @discord.ui.button(label="Odaya girişleri kapat", style=discord.ButtonStyle.danger)
    async def close_room(self, interaction: discord.Interaction, button: Button):
        channel = interaction.guild.get_channel(self.channel_id)
        await channel.set_permissions(interaction.guild.default_role, connect=False)
        await log_action(interaction.guild, f"🚫 {interaction.user.display_name} odaya girişleri kapattı", color=discord.Color.red())
        await interaction.response.send_message("🚫 Odaya girişler kapatıldı.", ephemeral=True)
        await update_panel(channel)

    @discord.ui.button(label="Odaya izin ver", style=discord.ButtonStyle.success)
    async def allow_user(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MentionUserModal(title="Odaya izin ver", action="allow", channel_id=self.channel_id))

    @discord.ui.button(label="Kullanıcıyı yasakla", style=discord.ButtonStyle.danger)
    async def ban_user(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MentionUserModal(title="Kullanıcıyı yasakla", action="ban", channel_id=self.channel_id))

    @discord.ui.button(label="Kapasiteyi Ayarla", style=discord.ButtonStyle.primary)
    async def set_limit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(LimitModal(channel_id=self.channel_id))

    @discord.ui.button(label="Oda Adını Değiştir", style=discord.ButtonStyle.secondary)
    async def rename_room(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RenameChannelModal(channel_id=self.channel_id))

# Panel güncelleme fonksiyonu / EN: Panel update function
async def update_panel(channel: discord.VoiceChannel):
    if channel.id not in private_channels:
        return
    owner_id = private_channels[channel.id]["owner_id"]
    message = private_channels[channel.id]["message"]
    member_count = len(channel.members)
    member_list = ", ".join([m.display_name for m in channel.members]) if member_count > 0 else "Kimse yok"
    embed = discord.Embed(
        title="🎧 Özel Odanı Yönet",
        description=f"**Oda:** {channel.name}\n**Kapasite:** {channel.user_limit}\n**Kullanıcılar:** {member_list}",
        color=discord.Color.blurple()
    )
    try:
        await message.edit(embed=embed)
    except:
        pass

# Botun belirlenen ses kanalında beklemesi / EN: Bot waiting in the designated voice channel
@bot.event
async def on_ready():
    print(f"{bot.user} giriş yaptı!")
    guild = bot.guilds[0]
    wait_channel = guild.get_channel(WAIT_CHANNEL_ID)
    if wait_channel and isinstance(wait_channel, discord.VoiceChannel):
        try:
            await wait_channel.connect()
            print(f"{bot.user} {wait_channel.name} kanalında bekliyor.")
        except Exception as e:
            print(f"Ses kanalına bağlanamadı: {e}")

# Özel oda oluşturma ve silme / EN: Create and delete private rooms
@bot.event
async def on_voice_state_update(member, before, after):
    guild = member.guild

    # Kullanıcı JOIN_TO_CREATE_CHANNEL_ID kanalına girerse / EN: If user joins the JOIN_TO_CREATE channel
    if after.channel and after.channel.id == JOIN_TO_CREATE_CHANNEL_ID:
        # Kullanıcının zaten özel bir odası var mı kontrol et / EN: Check if the user already has a private room
        if any(info["owner_id"] == member.id for info in private_channels.values()):
            for chan_id, info in private_channels.items():
                if info["owner_id"] == member.id:
                    existing_channel = guild.get_channel(chan_id)
                    if existing_channel:
                        await member.move_to(existing_channel)
                    return

        # Özel oda oluştur / EN: Create a private room
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            member: discord.PermissionOverwrite(connect=True, manage_channels=True)
        }
        private_channel = await guild.create_voice_channel(
            name=f"{member.display_name}’ın Odası",
            overwrites=overwrites,
            user_limit=DEFAULT_CAPACITY,
            category=after.channel.category
        )
        private_channels[private_channel.id] = {"owner_id": member.id, "message": None}

        await member.move_to(private_channel)

        embed = discord.Embed(
            title="🎧 Özel Odanı Yönet",
            description=f"**Oda:** {private_channel.name}\n**Kapasite:** {private_channel.user_limit}\n**Kullanıcılar:** {member.display_name}",
            color=discord.Color.blurple()
        )
        view = ManageRoomView(owner_id=member.id, channel_id=private_channel.id)
        message = await private_channel.send(f"{member.mention}", embed=embed, view=view)
        private_channels[private_channel.id]["message"] = message

        await log_action(guild, f"🆕 {member.display_name} yeni bir özel oda oluşturdu: {private_channel.name}")

    # Oda boş kaldığında sil / EN: Delete when the room is left empty
    if before.channel and before.channel.id in private_channels:
        if len(before.channel.members) == 0:
            info = private_channels.pop(before.channel.id)
            try:
                await before.channel.delete()
            except Exception as e:
                print(f"Kanal silinirken hata: {e}")
            owner = guild.get_member(info["owner_id"])
            if owner:
                await log_action(guild, f"🗑️ {owner.display_name}’ın odası boş kaldığı için silindi.")

# Botu çalıştır / EN: Run the bot
bot.run("BURAYA TOKENİ YAZ! PASTE YOUR BOT TOKEN") #Bot Token