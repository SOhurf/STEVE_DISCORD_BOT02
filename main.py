import discord
import aiohttp
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv
import json
import random
from keep_alive import keep_alive
from bs4 import BeautifulSoup
import time
from datetime import datetime

# LOADING BOT AND MAIN VARS #
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

filePath = "/app/data/data.json" 
levelUpChannelId = 1459662203102957645
startTime = datetime.now()

if not token:
    print("❌ ERROR: No DISCORD_TOKEN found in environment variables.")
    exit()

# SETTING INTENTS #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

# CREATING BOT #
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

# DATA #
def load_data():
    if os.path.exists(filePath):
        try:
            with open(filePath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_data(data):
    try:
        with open(filePath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"❌ Błąd zapisu danych: {e}")

def format_uptime(delta):
    seconds = int(delta.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days > 0:
        parts.append(f"{days}dni")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    if not parts:
        return "przed chwilą"
        
    return " ".join(parts)

# BACKGROUND VOICE LOOP #
@tasks.loop(minutes=1.5)
async def give_voice_xp():
    data = load_data()
    updated = False
    
    for guild in bot.guilds:
        for voice_channel in guild.voice_channels:
            for member in voice_channel.members:
                if member.bot: continue 
                
                user = next((m for m in data if m["id"] == member.id), None)
                if user:
                    user["exp"] += 60
                    updated = True
                    
                    xp_needed = user["level"] * 100
                    if user["exp"] >= xp_needed:
                        user["level"] += 1
                        user["exp"] = 0
                        
                        level_chan = bot.get_channel(levelUpChannelId)
                        if level_chan:
                            await level_chan.send(f"🎊 **{member.mention} awansował na poziom {user['level']} (Voice) !**")
                        
                        role_name = None
                        if user["level"] >= 50: role_name = "Level 50⛏️"
                        elif user["level"] >= 40: role_name = "Level 40🧢"
                        elif user["level"] >= 35: role_name = "Level 35🤠"
                        elif user["level"] >= 30: role_name = "Level 30👨‍💻"
                        elif user["level"] >= 25: role_name = "Level 25🔨"
                        elif user["level"] >= 20: role_name = "Level 20💗"
                        elif user["level"] >= 15: role_name = "Level 15💪"
                        elif user["level"] >= 10: role_name = "Level 10👷‍♂️"
                        elif user["level"] >= 5: role_name = "Level 5👷"
                        
                        if role_name:
                            role = discord.utils.get(guild.roles, name=role_name)
                            if role and role not in member.roles:
                                await member.add_roles(role)

    if updated:
        save_data(data)

# STATUS #
@tasks.loop(minutes=1)
async def update_status():
    currentTime = datetime.now()
    uptime = currentTime - startTime 

    readableTime = format_uptime(uptime)
    await bot.change_presence(activity=discord.Game(name=f"Online od: {readableTime}"))

@update_status.before_loop
async def before_update_status():
    await bot.wait_until_ready()
# BOT EVENTS #
@bot.event
async def on_ready():
    print(f"✅ Bot jest online jako {bot.user} (ID: {bot.user.id})")

    if not update_status.is_running():
        update_status.start()
    
    if not give_voice_xp.is_running():
        give_voice_xp.start()
    
    memberData = load_data()
    existing_ids = [m["id"] for m in memberData]
    
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot or member.id in existing_ids:
                continue

            memberData.append({
                "username": member.name,
                "id": member.id,
                "joined_date": member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown",
                "avatar": member.avatar.url if member.avatar else None,
                "exp": 0,
                "level": 1,
                "is_bot": member.bot,
                "has_admin_permissions": member.guild_permissions.administrator,
            })
    save_data(memberData)
    print(f"📂 Zsynchronizowano bazę danych {filePath}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or message.content.startswith(("!", "/")):
        await bot.process_commands(message)
        return

    data = load_data()
    user = next((m for m in data if m["id"] == message.author.id), None)
    
    if user:
        user["exp"] += random.randint(30, 60)
        xpNeeded = user["level"] * 100
        
        if user["exp"] >= xpNeeded:
            user["level"] += 1
            user["exp"] = 0
            
            levelChannel = bot.get_channel(levelUpChannelId)
            if levelChannel:
                await levelChannel.send(f"🎊 **{message.author.mention} awansował na poziom {user['level']} (Chat) !**")
            
            role_name = None
            if user["level"] >= 50: role_name = "Level 50⛏️"
            elif user["level"] >= 40: role_name = "Level 40🧢"
            elif user["level"] >= 30: role_name = "Level 30👨‍💻"
            elif user["level"] >= 20: role_name = "Level 20💗"
            elif user["level"] >= 10: role_name = "Level 10👷‍♂️"
            elif user["level"] >= 5: role_name = "Level 5👷"
            
            if role_name:
                role = discord.utils.get(message.guild.roles, name=role_name)
                if role and role not in message.author.roles:
                    await message.author.add_roles(role)
        
        save_data(data)
    await bot.process_commands(message)

# CLASSES #
class MinesweeperButton(discord.ui.Button):
    def __init__(self, x, y, is_mine, neighbor_count):
        # We use row=y to keep the 3x3 grid shape
        super().__init__(label="?", style=discord.ButtonStyle.secondary, row=y)
        self.x = x
        self.y = y
        self.is_mine = is_mine
        self.neighbor_count = neighbor_count

    async def callback(self, interaction: discord.Interaction):
        # Owner Check
        if interaction.user.id != self.view.owner_id:
            return await interaction.response.send_message("**❌To nie twoja gra!**", ephemeral=True)

        if self.is_mine:
            await self.view.end_game(interaction, won=False)
        else:
            self.style = discord.ButtonStyle.success
            self.label = str(self.neighbor_count) if self.neighbor_count > 0 else "0"
            self.disabled = True
            
            # Logic to check for win
            self.view.safe_tiles_cleared += 1
            if self.view.safe_tiles_cleared == (3 * 3 - self.view.num_mines):
                await self.view.end_game(interaction, won=True)
            else:
                # Update the visual grid in the embed
                await interaction.response.edit_message(embed=self.view.create_embed(), view=self.view)

class MinesweeperGame(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.grid_size = 3
        self.num_mines = 2
        self.safe_tiles_cleared = 0
        self.game_over = False
        self.won = False
        self.create_board()

    def create_board(self):
        # Initialize 3x3 grid
        self.board_data = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        mine_slots = random.sample(range(9), self.num_mines)
        
        for slot in mine_slots:
            self.board_data[slot // 3][slot % 3] = -1

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                is_mine = self.board_data[y][x] == -1
                count = self.get_neighbors(x, y) if not is_mine else 0
                self.add_item(MinesweeperButton(x, y, is_mine, count))

    def get_neighbors(self, x, y):
        count = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < 3 and 0 <= ny < 3:
                    if self.board_data[ny][nx] == -1:
                        count += 1
        return count

    def create_embed(self):
        color = discord.Color.blue()
        status = "**Gra trwa!**"

        if self.game_over:
            color = discord.Color.green() if self.won else discord.Color.red()
            status = "!" if self.won else "**💥 KABOOM!**"

        embed = discord.Embed(title="Saper👷‍♂️", color=color)
        embed.description = f"**Status:** `{status}`\n**Właściciel:** <@{self.owner_id}>\n\n"
        
        grid_text = ""
        for child in self.children:
            if isinstance(child, MinesweeperButton):
                if child.disabled or self.game_over:
                    if child.is_mine: grid_text += "💣 "
                    elif child.label == "0": grid_text += "⬛ "
                    else: grid_text += f"{child.label}️⃣ "
                else:
                    grid_text += "❓ "
            if child.x == 2: grid_text += "\n" # New line every 3 buttons
            
        embed.add_field(name="Plansza", value=grid_text)
        embed.set_footer(text="Kliknij w przycisk aby zacząć grę!")
        return embed

    async def end_game(self, interaction, won):
        self.game_over = True
        self.won = won
        for child in self.children:
            child.disabled = True
            if child.is_mine:
                child.style = discord.ButtonStyle.danger
                child.label = "💣"
        
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


# BOT COMMANDS #
@bot.command()
async def profil(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_data()
    user_data = next((m for m in data if m["id"] == member.id), None)

    if user_data:
        xp_limit = user_data["level"] * 100
        embed = discord.Embed(
            title=f"**Profil Gracza: `{user_data['username']}`👷‍♂️**",
            description=f"**Poziom: `{user_data['level']}`**\n"
                        f"**EXP: `{user_data['exp']}/{xp_limit}`**\n"
                        f"**ID: `{user_data['id']}`**",
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

@bot.command()
async def pomoc(ctx):
    commands_list = [
        "**!profil <@użytkownik>** - Pokazuje profil.",
        "**!avatar <@użytkownik>** - Pokazuje awatar.",
        "**!toplevel** - Pokazuje topka graczy (level).",
        "**!saper** - Klasyczna gra w sapera.",
        "\n**--- KOMENDY ADMINISTRACYJNE 🔨 ---**",
        "**!clear <ilość>** - Usuwa wiadomości.",
    ]
    embed = discord.Embed(
        title="**Dostępne Komendy👷‍♂️**",
        description="\n".join(commands_list),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_role("Papej🔨")
async def clear(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"**Usunięto {len(deleted) - 1} wiadomości.**", delete_after=1.5)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"**Avatar Gracza {member.name}:**\n{member.display_avatar.url}")

@bot.command()
async def rozsypanka(ctx, *words: str):
    word_list = list(words)
    random.shuffle(word_list)
    await ctx.send(f"**{' '.join(word_list)}**")

@bot.command(aliases=["top", "ranking"])
async def toplevel(ctx):
    data = load_data()
    leaderBoardData = sorted(data, key=lambda x: (x["level"], x["exp"]), reverse=True)
    top10 = leaderBoardData[:10]
    description = ""

    for index, user in enumerate(top10, start=1):
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"**{index}.**"
        description += f"{medal} **{user['username']}** - Poziom: `{user['level']}` (XP: `{user['exp']}`)\n"

    embed = discord.Embed(title="🏆 **Top 10 Graczy**", description=description or "Brak danych.", color=discord.Color.gold())
    await ctx.send(embed=embed)
    
@bot.command()
async def saper(ctx):
    view = MinesweeperGame(ctx.author.id)
    await ctx.send(embed=view.create_embed(), view=view)

# RUN #
keep_alive()
try:
    bot.run(token)
except discord.errors.HTTPException as e:
    print(f"❌ Błąd logowania: {e}")





















