import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import random
import json
import os
from typing import Dict, Tuple

# ------------------------------
# Sabitler
# ------------------------------
# ------------------------------
# Constants
# ------------------------------
LOG_KANALI_ID = 1111111111111111111   # Log kanalı ID
# Log channel ID
GUILD_ID = 1111111111111111111       # Sunucu ID
# Server (guild) ID
AFK_KANALI_ID = 1111111111111111111 # AFK kanal ID
# AFK channel ID
TIMEOUTS_FILE = "timeouts.json"      # Timeout kayıt dosyası
# Timeouts record file

# ------------------------------
# Intents
# ------------------------------
# ------------------------------
# Intents (bot permissions)
# ------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# aktif_timeouts: {user_id: (end_datetime_utc, guild_id)}
# active_timeouts: {user_id: (end_datetime_utc, guild_id)}
aktif_timeouts: Dict[int, Tuple[datetime, int]] = {}

# ------------------------------
# Yardımcı Fonksiyonlar
# ------------------------------
# ------------------------------
# Helper Functions
# ------------------------------
async def log_embed(guild: discord.Guild, title: str, description: str, renk: discord.Color):
    kanal = guild.get_channel(LOG_KANALI_ID)
    if kanal is None:
        print(f"⚠️ Log kanalı bulunamadı! ID: {LOG_KANALI_ID}")
        # ⚠️ Log channel not found! ID: ...
        return
    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=renk,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Sunucu: {guild.name}")
        # Footer: Server: {guild.name}
        await kanal.send(embed=embed)
    except Exception as e:
        print(f"⚠️ Log gönderilemedi: {e}")
        # ⚠️ Failed to send log: {e}

def check_permissions(interaction: discord.Interaction, hedef: discord.Member) -> bool:
    # hedef.top_role < interaction.guild.me.top_role
    # returns True if target's top role is lower than the bot's top role
    if interaction.guild is None or interaction.guild.me is None:
        return False
    return hedef.top_role < interaction.guild.me.top_role

def kaydet_timeouts():
    try:
        with open(TIMEOUTS_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): (v[0].isoformat(), v[1]) for k, v in aktif_timeouts.items()}, f)
        # Save active timeouts to file
    except Exception as e:
        print(f"⚠️ Timeouts kaydedilemedi: {e}")
        # ⚠️ Could not save timeouts: {e}

def yukle_timeouts():
    if os.path.exists(TIMEOUTS_FILE):
        try:
            with open(TIMEOUTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    try:
                        dt = datetime.fromisoformat(v[0])
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        aktif_timeouts[int(k)] = (dt, int(v[1]))
                    except Exception:
                        continue
            print(f"🔁 {len(aktif_timeouts)} timeout kaydı yüklendi.")
            # 🔁 {n} timeout records loaded.
        except Exception as e:
            print(f"⚠️ Timeouts yüklenirken hata: {e}")
            # ⚠️ Error loading timeouts: {e}

# ------------------------------
# AFK kanalına bağlanma fonksiyonu
# ------------------------------
# ------------------------------
# Function to connect to AFK voice channel
# ------------------------------
async def baglan_sese():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("⚠️ Sunucu bulunamadı.")
        # ⚠️ Guild not found.
        return

    kanal = guild.get_channel(AFK_KANALI_ID)
    if not kanal:
        print("⚠️ AFK kanalı bulunamadı.")
        # ⚠️ AFK channel not found.
        return

    if guild.voice_client and guild.voice_client.is_connected():
        print("🔄 Bot zaten bir ses kanalına bağlı.")
        # 🔄 Bot is already connected to a voice channel.
        return

    try:
        vc = await kanal.connect(timeout=10.0)
        # İstersen botu kendi kendine sağırlaştır:
        # If you want, self-deafen the bot:
        await vc.guild.change_voice_state(channel=kanal, self_deaf=True)
        print(f"🎧 AFK kanalına başarıyla bağlanıldı: {kanal.name}")
        # 🎧 Successfully connected to AFK channel: {kanal.name}
    except Exception as e:
        print(f"⚠️ AFK kanalına bağlanılamadı: {e}")
        # ⚠️ Could not connect to AFK channel: {e}

# ------------------------------
# Bot hazır olduğunda
# ------------------------------
# ------------------------------
# When the bot is ready
# ------------------------------
@bot.event
async def on_ready():
    print(f"✅ {bot.user} giriş yaptı!")
    # ✅ {bot.user} has logged in!

    try:
        guild_obj = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild_obj)
        print("✅ Slash komutları senkronize edildi!")
        # ✅ Slash commands synchronized!
    except Exception as e:
        print(f"⚠️ Slash komut senkronizasyon hatası: {e}")
        # ⚠️ Slash command sync error: {e}

    yukle_timeouts()
    await baglan_sese()  # 🔊 AFK kanalına bağlan
    # 🔊 Connect to AFK channel

    afk_kontrol.start()
    kontrol_timeouts.start()

# ------------------------------
# Moderasyon Komutları
# ------------------------------
# ------------------------------
# Moderation Commands
# ------------------------------
@tree.command(name="sil", description="Belirtilen sayıda mesajı siler.")
@app_commands.describe(miktar="Silinecek mesaj sayısı")
async def sil(interaction: discord.Interaction, miktar: int):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("🚫 Bu komutu kullanma iznin yok.", ephemeral=True)
    if miktar < 1:
        return await interaction.response.send_message("❌ En az 1 mesaj silmelisin.", ephemeral=True)

    # interaction.channel purge requires a TextChannel; ensure it's a channel with purge
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("🚫 Bu komut bir metin kanalında kullanılmalı.", ephemeral=True)

    deleted = await channel.purge(limit=miktar)
    await interaction.response.send_message(f"✅ {len(deleted)} mesaj silindi.", ephemeral=True)
    await log_embed(interaction.guild, "🧹 Mesajlar Silindi",
                    f"Yetkili: {interaction.user.mention}\nKanal: {channel.mention}\nSilinen Mesaj: **{len(deleted)}**",
                    discord.Color.orange())
    # Log: Messages Deleted

@tree.command(name="kick", description="Bir kullanıcıyı sunucudan atar.")
@app_commands.describe(kullanici="Atılacak kullanıcı", sebep="Sebep (isteğe bağlı)")
async def kick(interaction: discord.Interaction, kullanici: discord.Member, sebep: str = "Belirtilmedi"):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("🚫 Bu komutu kullanma iznin yok.", ephemeral=True)
    if not check_permissions(interaction, kullanici):
        return await interaction.response.send_message("🚫 Bu kullanıcıyı atma yetkim yok.", ephemeral=True)
    try:
        await kullanici.kick(reason=sebep)
        await interaction.response.send_message(f"✅ {kullanici.mention} sunucudan atıldı.", ephemeral=True)
        await log_embed(interaction.guild, "👢 Kullanıcı Atıldı",
                        f"Yetkili: {interaction.user.mention}\nHedef: {kullanici.mention}\nSebep: {sebep}",
                        discord.Color.red())
        # Log: User Kicked
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Hata: {e}", ephemeral=True)

@tree.command(name="ban", description="Bir kullanıcıyı yasaklar.")
@app_commands.describe(kullanici="Yasaklanacak kullanıcı", sebep="Sebep (isteğe bağlı)")
async def ban(interaction: discord.Interaction, kullanici: discord.Member, sebep: str = "Belirtilmedi"):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("🚫 Bu komutu kullanma iznin yok.", ephemeral=True)
    if not check_permissions(interaction, kullanici):
        return await interaction.response.send_message("🚫 Bu kullanıcıyı yasaklama yetkim yok.", ephemeral=True)
    try:
        await kullanici.ban(reason=sebep)
        await interaction.response.send_message(f"✅ {kullanici.mention} yasaklandı.", ephemeral=True)
        await log_embed(interaction.guild, "🔨 Kullanıcı Yasaklandı",
                        f"Yetkili: {interaction.user.mention}\nHedef: {kullanici.mention}\nSebep: {sebep}",
                        discord.Color.dark_red())
        # Log: User Banned
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Hata: {e}", ephemeral=True)

@tree.command(name="unban", description="Bir kullanıcının yasağını kaldırır.")
@app_commands.describe(kullanici="Kullanıcının ID'si", sebep="Sebep (isteğe bağlı)")
async def unban(interaction: discord.Interaction, kullanici: str, sebep: str = "Belirtilmedi"):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("🚫 Bu komutu kullanma iznin yok.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(kullanici))
        await interaction.guild.unban(user, reason=sebep)
        await interaction.response.send_message(f"✅ {user.mention} adlı kullanıcının yasağı kaldırıldı.", ephemeral=True)
        await log_embed(interaction.guild, "🕊️ Yasak Kaldırıldı",
                        f"Yetkili: {interaction.user.mention}\nKullanıcı: {user.mention}\nSebep: {sebep}",
                        discord.Color.green())
        # Log: Unban
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Hata: {e}", ephemeral=True)
        # ⚠️ Error: {e}

@tree.command(name="timeout", description="Bir kullanıcıyı belirli süreliğine susturur.")
@app_commands.describe(kullanici="Susturulacak kullanıcı", dakika="Kaç dakika susturulsun?", sebep="Sebep (isteğe bağlı)")
async def timeout(interaction: discord.Interaction, kullanici: discord.Member, dakika: int, sebep: str = "Belirtilmedi"):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("🚫 Bu komutu kullanma iznin yok.", ephemeral=True)
    if not check_permissions(interaction, kullanici):
        return await interaction.response.send_message("🚫 Bu kullanıcıyı susturma yetkim yok.", ephemeral=True)
    if dakika <= 0:
        return await interaction.response.send_message("❌ Süre 1 dakikadan büyük olmalı.", ephemeral=True)

    sure = timedelta(minutes=dakika)
    bitis_zamani = datetime.now(timezone.utc) + sure
    try:
        # Discord.py modern approach: edit member timed_out_until
        await kullanici.edit(timed_out_until=bitis_zamani, reason=sebep)
        aktif_timeouts[kullanici.id] = (bitis_zamani, interaction.guild.id)
        kaydet_timeouts()
        await interaction.response.send_message(f"✅ {kullanici.mention} {dakika} dakika susturuldu.", ephemeral=True)
        await log_embed(interaction.guild, "🤐 Kullanıcı Susturuldu",
                        f"Yetkili: {interaction.user.mention}\nHedef: {kullanici.mention}\nSüre: {dakika} dk\nSebep: {sebep}",
                        discord.Color.gold())
        # Log: User Timed Out
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Hata: {e}", ephemeral=True)

@tree.command(name="untimeout", description="Bir kullanıcının susturmasını kaldırır.")
@app_commands.describe(kullanici="Susturması kaldırılacak kullanıcı")
async def untimeout(interaction: discord.Interaction, kullanici: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("🚫 Bu komutu kullanma iznin yok.", ephemeral=True)
    if not check_permissions(interaction, kullanici):
        return await interaction.response.send_message("🚫 Bu kullanıcıyı yönetme yetkim yok.", ephemeral=True)
    try:
        await kullanici.edit(timed_out_until=None)
        aktif_timeouts.pop(kullanici.id, None)
        kaydet_timeouts()
        await interaction.response.send_message(f"✅ {kullanici.mention} artık susturulmadı.", ephemeral=True)
        await log_embed(interaction.guild, "🔓 Susturma Kaldırıldı",
                        f"Yetkili: {interaction.user.mention}\nKullanıcı: {kullanici.mention}",
                        discord.Color.green())
        # Log: Timeout Removed
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Hata: {e}", ephemeral=True)

# ------------------------------
# Döngüler
# ------------------------------
# ------------------------------
# Loops / Tasks
# ------------------------------
@tasks.loop(seconds=60)
async def kontrol_timeouts():
    simdi = datetime.now(timezone.utc)
    for kullanici_id, (bitis, guild_id) in list(aktif_timeouts.items()):
        if simdi >= bitis:
            guild = bot.get_guild(guild_id)
            if guild:
                uye = guild.get_member(kullanici_id)
                if uye:
                    try:
                        await uye.edit(timed_out_until=None)
                        await log_embed(guild, "✅ Timeout Sona Erdi",
                                        f"{uye.mention} adlı kullanıcının susturulma süresi doldu.",
                                        discord.Color.green())
                        # Log: Timeout Ended
                    except Exception as e:
                        print(f"⚠️ Timeout kaldırılamadı: {e}")
                        # ⚠️ Could not remove timeout: {e}
            aktif_timeouts.pop(kullanici_id, None)
            kaydet_timeouts()

@tasks.loop(seconds=60)
async def afk_kontrol():
    guild = bot.get_guild(GUILD_ID)
    if guild:
        kanal = guild.get_channel(AFK_KANALI_ID)
        if kanal:
            ses = guild.voice_client
            if ses is None or not ses.is_connected():
                try:
                    vc = await kanal.connect()
                    await vc.guild.change_voice_state(channel=kanal, self_deaf=True)
                    print("🎧 AFK kanalına yeniden bağlandı.")
                    # 🎧 Reconnected to AFK channel.
                except Exception as e:
                    print(f"⚠️ AFK kanalına bağlanamadı: {e}")
                    # ⚠️ Could not reconnect to AFK channel: {e}

# ------------------------------
# Eğlence Komutları
# ------------------------------
# ------------------------------
# Fun / Entertainment Commands
# ------------------------------
@tree.command(name="zar", description="1 ile 6 arasında zar atar.")
async def zar(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 Zar sonucu: **{random.randint(1,6)}**")
    # 🎲 Dice roll result

@tree.command(name="yazitura", description="Yazı tura atar.")
async def yazitura(interaction: discord.Interaction):
    sonuc = "Yazı" if random.randint(0,1) == 0 else "Tura"
    await interaction.response.send_message(f"💰 Sonuç: **{sonuc}**")
    # 💰 Result: Heads or Tails

# ------------------------------
# Botu çalıştır
# ------------------------------
# ------------------------------
# Run the bot
# ------------------------------
TOKEN = ""  # Bot tokeninizi buraya girin / Enter your bot token here
bot.run(TOKEN)