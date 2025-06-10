import discord
from discord.ext import commands, tasks
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()



intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.message_content = True
bot_token = os.getenv("DISCORD_BOT_TOKEN")

bot = commands.Bot(command_prefix='!', intents=intents)
firstRun = True

# Channel ID to monitor
CHANNEL_ID = 422297340356067329  # Replace with your channel ID
REACTION_DATA_FILE = "reaction_counts.txt"

# Specify the day of the week to send the report (0=Monday, 1=Tuesday, ..., 6=Sunday)
REPORT_DAY = 6  # Replace with the desired day, e.g., 6 for Sunday

# The emoji the bot will react with (can be Unicode or custom)
TARGET_EMOJI = "⬆️"  # Replace with your desired emoji (e.g., "<:emoji_name:emoji_id>" for custom emojis)

reaction_data = {}

# Load reaction data from file
def load_reaction_data():
    if os.path.exists(REACTION_DATA_FILE):
        with open(REACTION_DATA_FILE, "r") as f:
            for line in f:
                message_id, count = line.strip().split()
                reaction_data[int(message_id)] = int(count)

# Save reaction data to file
def save_reaction_data():
    with open(REACTION_DATA_FILE, "w") as f:
        for message_id, count in reaction_data.items():
            f.write(f"{message_id} {count}\n")

# Monitor the channel for images or videos and react with the specified emoji
@bot.event
async def on_message(message):
    if message.channel.id == CHANNEL_ID and (message.attachments or any(embed.type in ['image', 'video'] for embed in message.embeds)):
        # React with the specific emoji
        await message.add_reaction(TARGET_EMOJI)

        # Initialize the reaction count for the message
        reaction_data[message.id] = 0
        save_reaction_data()

# Track reactions, only counting those with the specific emoji
@bot.event
async def on_reaction_add(reaction, user):
    if reaction.message.id in reaction_data and str(reaction.emoji) == TARGET_EMOJI:
        # Get unique users who reacted with the TARGET_EMOJI
        unique_users = set()

        # Asynchronously iterate through the users who reacted with the specific emoji
        async for reacting_user in reaction.users():
            unique_users.add(reacting_user)

        # Update the reaction count for the message
        reaction_data[reaction.message.id] = len(unique_users)
        save_reaction_data()

# Weekly report on a specific day
@tasks.loop(hours=24)  # Loop every 24 hours to check if it's the report day
async def weekly_report():

    global firstRun

    if datetime.now().weekday() == REPORT_DAY:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            return

        max_reactions = 0
        max_message_id = None

        # Find the message with the most reactions
        for message_id, count in reaction_data.items():
            if count > max_reactions:
                max_reactions = count
                max_message_id = message_id

        if max_message_id:
            message = await channel.fetch_message(max_message_id)  # Fetching the message with most reactions
            message_author = message.author  # Finding the author of the message

            if message.attachments:
                await channel.send(
                    f"The Solution of the Week is by {message_author.mention}! You have earned the Post of the Week role. Enjoy it!: {message.jump_url} Winning post:",
                    file=await message.attachments[0].to_file()  # Posting the image of the solution
                )
            
        
        today_date = datetime.today().strftime('%Y-%m-%d')

        with open("reaction_counts.txt", 'r') as source:
            content = source.read()

        with open("all_reaction_count_data.txt", 'a') as destination:
            destination.write(f"\nDate: {today_date}\n")
            destination.write(content)

        with open(REACTION_DATA_FILE, "w") as f:
            pass  # Clear the contents

        reaction_data.clear()

        firstRun = True

# Start the weekly report loop after the bot is ready
@bot.event
async def on_ready():
    load_reaction_data()
    weekly_report.start()
    print(f'Logged in as {bot.user}')

# Run the bot
bot.run (bot_token)