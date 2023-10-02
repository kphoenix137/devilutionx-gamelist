import discord
import json
import time
import asyncio
import datetime
import math
import re
from typing import Optional

# Constants
DISCORD_CHANNEL_ID = 1061483226767556719

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
current_online = 0
global_online_list_message = None
global_channel: Optional[discord.TextChannel] = None
gameTTL = 120  # games are marked as active for x seconds every time they show up


def escape_discord_formatting_characters(text: str):
    return re.sub(r'([-\\*_#|~:@[\]()<>`])', r'\\\1', text)


async def format_game(game):
    embed = {
        "type": "rich",
        "title": game['id'].upper(),
        "description": "",
        "color": 0x00ff00,
        "fields": [],
        "thumbnail": {
            "url": "",
            "height": 0,
            "width": 0
        },
        "author": {
            "name": f"DevilutionX {game['version']}"
        },
        "footer": {
            "text": f"Duration: {format_time_delta(round((time.time() - game['first_seen']) / 60))}"
        }
    }

    # Checking if the game is ended to adjust border color
    if time.time() - game['last_seen'] >= gameTTL:
        embed["color"] = 0xff0000  # red for closed games

    # Players
    embed["fields"].append({
        "name": "Players",
        "value": ', '.join([name for name in game['players']]),
        "inline": True
    })

    # Difficulty
    difficulties = ["Normal", "Nightmare", "Hell"]
    embed["fields"].append({
        "name": "Difficulty",
        "value": difficulties[game['difficulty']],
        "inline": True
    })

    # Game Speed
    tick_rate_mapping = {
        20: "Normal",
        30: "Fast",
        40: "Faster",
        50: "Fastest"
    }
    speed = tick_rate_mapping.get(game['tick_rate'], f"Speed: {game['tick_rate']}")
    embed["fields"].append({
        "name": "Game Speed",
        "value": speed,
        "inline": True
    })

    # Game Options
    diablo_game_codes = {'DRTL', 'DSHR', 'IRON', 'MEMD', 'DWKD', 'LTDR', 'LTDS'}
    attributes = []
    if game['run_in_town']:
        attributes.append('Run in Town')
    if game['full_quests']:
        attributes.append('Quests')
    if game['theo_quest'] and game['type'] not in diablo_game_codes:
        attributes.append('Theo Quest')
    if game['cow_quest'] and game['type'] not in diablo_game_codes:
        attributes.append('Cow Quest')
    if game['friendly_fire']:
        attributes.append('Friendly Fire')

    if attributes:
        embed["fields"].append({
            "name": "Game Options",
            "value": ', '.join(attributes),
            "inline": True
        })

    # Thumbnail based on game type
    game_type_icons = {
        'DRTL': 'URL',  # DevilutionX Diablo Retail
        'DSHR': 'URL',  # DevilutionX Diablo Shareware
        'HRTL': 'URL',  # DevilutionX Hellfire Retail
        'HSHR': 'URL',  # DevilutionX Hellfire Shareware
        'IRON': 'URL',  # Ironman Diablo Retail (Sixcy)
        'MEMD': 'URL',  # Middle Earth Diablo Retail (DakkJaniels)
        'DRDX': 'URL',  # DiabloX Diablo Retail (ikonomov)
        'DWKD': 'URL',  # wkdmod Diablo Retail (wkdgmr)
        'HWKD': 'URL',  # wkdmod Hellfire Retail (wkdgmr)
        'LTDR': 'URL',  # Lord of Terror Diablo Retail (kphoenix)
        'LTDS': 'URL',  # Lord of Terror Diablo Shareware (kphoenix)
        'LTHR': 'URL',  # Lord of Terror Hellfire Retail (kphoenix)
        'LTHS': 'URL',  # Lord of Terror Hellfire Shareware (kphoenix)
    }
    embed["thumbnail"]["url"] = game_type_icons.get(game['type'], "")

    return embed


async def update_status_message():
    global current_online
    global global_channel
    global global_online_list_message
    if global_online_list_message is not None:
        try:
            await global_online_list_message.delete()
        except discord.errors.NotFound:
            pass
        global_online_list_message = None
    text = 'There are currently **' + str(current_online) + '** public games.'
    if current_online == 1:
        text = 'There is currently **' + str(current_online) + '** public game.'
    assert isinstance(global_channel, discord.TextChannel)
    global_online_list_message = await global_channel.send(text)


async def update_game_message(game_id):
    global global_channel
    text = format_game(game_list[game_id])
    if 'message' in game_list[game_id]:
        if game_list[game_id]['message'].content != text:
            try:
                await game_list[game_id]['message'].edit(content=text)
            except discord.errors.NotFound:
                pass
        return
    assert isinstance(global_channel, discord.TextChannel)
    game_list[game_id]['message'] = await global_channel.send(text)


def format_time_delta(minutes):
    if minutes < 2:
        return '1 minute'
    elif minutes < 60:
        return str(minutes) + ' minutes'

    text = ''
    if minutes < 120:
        text += '1 hour'
        minutes -= 60
    else:
        hours = math.floor(minutes / 60)
        text += str(hours) + ' hours'
        minutes -= hours * 60

    if minutes > 0:
        text += ' and ' + format_time_delta(minutes)

    return text


async def end_game_message(game_id):
    if 'message' in game_list[game_id]:
        try:
            await game_list[game_id]['message'].edit(content=format_game(game_list[game_id]))
        except discord.errors.NotFound:
            pass


async def remove_game_messages(game_ids):
    for gameId in game_ids:
        if 'message' in game_list[gameId]:
            try:
                await game_list[gameId]['message'].delete()
            except discord.errors.NotFound:
                pass
            del game_list[gameId]['message']


def any_player_name_is_invalid(players):
    for name in players:
        # using the same restricted character list as DevilutionX, see
        #  https://github.com/diasurgical/devilutionX/blob/0eda8d9367e08cea08b2ad81e1ce534e927646d6/Source/DiabloUI/diabloui.cpp#L649
        if re.search(r'[,<>%&\\"?*#/: ]', name):
            return True

        for char in name:
            if ord(char) < 32 or ord(char) > 126:
                # ASCII control characters or anything outside the basic latin set aren't allowed
                #  in the current DevilutionX codebase, see
                #  https://github.com/diasurgical/devilutionX/blob/0eda8d9367e08cea08b2ad81e1ce534e927646d6/Source/DiabloUI/diabloui.cpp#L654
                return True

    return False


def any_player_name_contains_a_banned_word(players):
    with open('./banlist', 'r') as ban_list_file:
        words = set([line.strip().upper() for line in ban_list_file.read().split('\n') if line.strip()])

        for name in players:
            for word in words:
                if word in name.upper():
                    return True

    return False


game_list = {}
background_task_running = 0


async def background_task():
    global gameTTL
    global current_online
    last_refresh = 0
    refresh_seconds = 60  # refresh gamelist every x seconds
    while True:
        await asyncio.sleep(1)
        if time.time() - last_refresh >= refresh_seconds:
            last_refresh = time.time()
            # Call the external program and get the output
            proc = await asyncio.create_subprocess_shell(
                './devilutionx-gamelist',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)

            stdout, stderr = await proc.communicate()
            output = stdout.decode()
            if not output:
                continue

            # Load the output as a JSON list
            games = json.loads(output)

            ct = datetime.datetime.now()
            print('[' + str(ct) + '] Refreshing game list - ' + str(len(games)) + ' games')

            for game in games:
                if any_player_name_is_invalid(game['players']) or any_player_name_contains_a_banned_word(game['players']):
                    continue

                key = game['id'].upper()
                if key in game_list:
                    game_list[key]['players'] = game['players']
                    game_list[key]['last_seen'] = time.time()
                    continue

                game_list[key] = game
                game_list[key]['first_seen'] = time.time()
                game_list[key]['last_seen'] = time.time()

            ended_games = []
            for key, game in game_list.items():
                if time.time() - game['last_seen'] < gameTTL:
                    continue
                ended_games.append(key)
                await end_game_message(key)

            for key in ended_games:
                del game_list[key]

            if len(ended_games) != 0:
                await remove_game_messages(game_list.keys())

            for gameId in game_list.keys():
                await update_game_message(gameId)

            if (current_online == len(game_list)) or len(ended_games) != 0:
                continue

            current_online = len(game_list)
            await update_status_message()

            activity = discord.Activity(name='Games online: '+str(current_online), type=discord.ActivityType.watching)
            await client.change_presence(activity=activity)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    global global_channel
    global_channel = client.get_channel(DISCORD_CHANNEL_ID)
    await background_task()

with open('./discord_bot_token', 'r') as file:
    token = file.readline()

client.run(token)
