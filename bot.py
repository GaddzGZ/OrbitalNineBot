import discord
from discord.ext import commands, tasks
import os
import json
from datetime import datetime, time, timedelta
from dotenv import load_dotenv
load_dotenv()


# Configuration
bot_token = os.getenv("DISCORD_BOT_TOKEN")
VOTING_CHANNEL_ID = 422297340356067329  # Channel for voting/counting/winner announcements
WELCOME_CHANNEL_ID = 672927574904668187  # Channel for welcome messages (change this!)
REPORT_TIME = time(12, 0)  # 12:00 PM
TARGET_EMOJI = "⬆️"
WELCOME_MESSAGE = "Welcome to the server, {mention}! 🎉"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Data management
def load_json(filename, default=None):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return default or {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

reaction_data = load_json("reaction_data.json")

def get_week_id():
    now = datetime.now()
    sunday = now - timedelta(days=(now.weekday() + 1) % 7)
    return sunday.strftime('%Y-W%U')

def should_report():
    now = datetime.now()
    return (now.weekday() == 6 and now.time() >= REPORT_TIME and 
            load_json("last_report.json").get('week') != get_week_id())

@bot.event
async def on_ready():
    if not weekly_report.is_running():
        weekly_report.start()

@bot.event
async def on_member_join(member):
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not welcome_channel:
        # Fallback to system channel or general
        welcome_channel = member.guild.system_channel or discord.utils.get(member.guild.text_channels, name='general')
    
    if welcome_channel:
        await welcome_channel.send(WELCOME_MESSAGE.format(mention=member.mention))

@bot.event
async def on_message(message):
    if (not message.author.bot and message.channel.id == VOTING_CHANNEL_ID and 
        (message.attachments or any(e.type in ['image', 'video'] for e in message.embeds))):
        await message.add_reaction(TARGET_EMOJI)
        reaction_data[str(message.id)] = 0
        save_json("reaction_data.json", reaction_data)
    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    msg_id = str(message.id)
    if msg_id in reaction_data:
        del reaction_data[msg_id]
        save_json("reaction_data.json", reaction_data)

@bot.event
async def on_reaction_add(reaction, user):
    if not user.bot and str(reaction.message.id) in reaction_data and str(reaction.emoji) == TARGET_EMOJI:
        users = [u async for u in reaction.users() if not u.bot]
        reaction_data[str(reaction.message.id)] = len(users)
        save_json("reaction_data.json", reaction_data)

@bot.event
async def on_reaction_remove(reaction, user):
    if not user.bot and str(reaction.message.id) in reaction_data and str(reaction.emoji) == TARGET_EMOJI:
        users = [u async for u in reaction.users() if not u.bot]
        reaction_data[str(reaction.message.id)] = len(users)
        save_json("reaction_data.json", reaction_data)

@tasks.loop(minutes=30)
async def weekly_report():
    if not should_report() or not reaction_data:
        return
    
    channel = bot.get_channel(VOTING_CHANNEL_ID)
    if not channel:
        return
    
    winner_id = max(reaction_data, key=reaction_data.get)
    max_reactions = reaction_data[winner_id]
    
    try:
        winner_msg = await channel.fetch_message(int(winner_id))
        file = await winner_msg.attachments[0].to_file() if winner_msg.attachments else None
        
        await channel.send(
            f"🏆 **Solution of the Week** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
            f"Goes to {winner_msg.author.mention} with {max_reactions} reactions!\n{winner_msg.jump_url}",
            file=file
        )
        
        winner_info = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'user_id': winner_msg.author.id,
            'username': str(winner_msg.author),
            'reactions': max_reactions,
            'message_url': winner_msg.jump_url
        }
    except:
        await channel.send(
            f"🏆 **Solution of the Week** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
            f"Winner had {max_reactions} reactions but message was deleted!"
        )
        winner_info = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'username': 'Unknown (deleted)',
            'reactions': max_reactions
        }
    
    # Archive data
    archives = load_json("weekly_archives.json", [])
    archives.append({'date': datetime.now().strftime('%Y-%m-%d'), 'data': reaction_data.copy(), 'winner': winner_info})
    save_json("weekly_archives.json", archives)
    
    # Save winner record
    winners = load_json("winners_record.json", [])
    winners.append(winner_info)
    save_json("winners_record.json", winners)
    
    # Mark as reported and reset
    save_json("last_report.json", {'week': get_week_id()})
    reaction_data.clear()
    save_json("reaction_data.json", reaction_data)

@bot.command()
async def standings(ctx):
    if ctx.channel.id != VOTING_CHANNEL_ID or not reaction_data:
        return
    
    standings = "📊 **Current Weekly Standings:**\n"
    sorted_data = sorted(reaction_data.items(), key=lambda x: x[1], reverse=True)[:5]
    
    for i, (msg_id, count) in enumerate(sorted_data, 1):
        try:
            msg = await ctx.channel.fetch_message(int(msg_id))
            standings += f"{i}. {msg.author.mention} - {count} reactions\n"
        except:
            continue
    
    await ctx.send(standings)

@bot.command()
async def winners(ctx):
    if ctx.channel.id != VOTING_CHANNEL_ID:
        return
    
    winners = load_json("winners_record.json", [])
    if not winners:
        await ctx.send("🏆 No winners recorded yet!")
        return
    
    history = "🏆 **Recent Winners:**\n"
    for winner in winners[-5:][::-1]:
        history += f"**{winner['date']}**: {winner['username']} ({winner['reactions']} reactions)\n"
    
    await ctx.send(history)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def botstatus(ctx):
    now = datetime.now()
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.time() >= REPORT_TIME:
        days_until_sunday = 7
    next_report = (now + timedelta(days=days_until_sunday)).replace(hour=12, minute=0, second=0)
    
    await ctx.send(
        f"🤖 **Bot Status:**\n"
        f"• Voting channel: <#{VOTING_CHANNEL_ID}> (tracking {len(reaction_data)} messages)\n"
        f"• Welcome channel: <#{WELCOME_CHANNEL_ID}>\n"
        f"• Reports: Sundays at 12:00 PM\n"
        f"• Next report: {next_report.strftime('%Y-%m-%d %H:%M')}\n"
        f"• Current week: {get_week_id()}"
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def forcereport(ctx):
    if ctx.channel.id != VOTING_CHANNEL_ID:
        return
    await ctx.send("🔄 Forcing report...")
    save_json("last_report.json", {'week': 'force'})  # Temporary override
    await weekly_report()
    await ctx.send("✅ Report completed!")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def cleanup(ctx):
    if ctx.channel.id != VOTING_CHANNEL_ID:
        return
    
    deleted = 0
    for msg_id in list(reaction_data.keys()):
        try:
            await ctx.channel.fetch_message(int(msg_id))
        except:
            del reaction_data[msg_id]
            deleted += 1
    
    if deleted:
        save_json("reaction_data.json", reaction_data)
    
    await ctx.send(f"✅ Cleaned up {deleted} deleted messages.")

if __name__ == "__main__":
    bot.run(bot_token)