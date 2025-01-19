import sys
import os
import toml
import traceback
import logging

try:

    toml_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "res", "config.toml")

    if not os.path.exists(toml_dir):

        url_add_flag = False
        urls = []
        urls_dict = {}
        sys.stdout.write("This is the process to start the NotificationChecker. Please follow the guide.\n")

        while not url_add_flag:
            tmp_url = input('1-1. [CLIENT] Put an url that you want to track. You can repeat to put the url unless you put the "0"'
                            '\nIf you finished, put the "0" and enter.\n▷  ')

            if tmp_url == "0":
                url_add_flag = True

            else:
                urls.append(tmp_url)

        sys.stdout.write("Now you have to name each urls. We'll show you an url that you gave.\n"
                         "Please put the name of the url. You can rename it after the initialization.\n")
        for url in urls:
            url_name = input(f"{url}\n> put the name or keyword of this website.:\n")
            urls_dict[url_name] = url

        discord_token = input('2-1. [DISCORD] Put the your discord token for this bot.\n▷  ')

        discord_guild_id = int(input('2-2. [DISCORD] Put the id of the guild where you want to operate this bot.\n▷  '))


        discord_channel_ids = {}
        channel_id_flag = True

        while channel_id_flag:
            tmp_channel_id = input('2-3. [DISCORD] Using "|" to divide the name and id, '
                                   'put the name and id of your channel where you want to operate this bot.'
                                   '[Example: "MAIN|channel_id"]\n'
                                   ' You can repeat to put the url unless you put the "0"'
                                   '\nIf you finished, put the "0" and enter.\n▷  ')

            if tmp_channel_id == "0":
                channel_id_flag = False
            else:
                tmp_name, tmp_id = tmp_channel_id.split("|")
                discord_channel_ids[tmp_name] = int(tmp_id)
        with open(toml_dir, "w", encoding="utf-8") as f:
            config_data = {
                'CLIENT' : {
                    'URLS' : urls,
                    'NEWEST_POST' : {key: {
                        'ID' : 'J0724',
                        'DATE' : '2003-07-24',
                        'URL': link
                    } for key, link in urls_dict.items()},
                },
                'DISCORD' : {
                    'TOKEN' : discord_token,  #  Put your token from discord bot
                    'GUILD_ID' : discord_guild_id,  #  Put your guild id where you want to send message
                    'COMMAND_PREFIX' : "!", #  Customize your command prefix
                    'INITIALIZED_FLAG' : True,
                    'EMOJIS': {
                        'CHECK' : [ "☑️", "✔️", "✅",],
                        'SAVE' : ["💾"],
                    },
                    'CHANNEL_ID' : discord_channel_ids,

                }
            }
            toml.dump(config_data, f)

        sys.stdout.write(f"config.toml has been initialized.\nYou can refactor the configuration file in the below path.\n(path: {toml_dir})\n")

except:
    logging.error(traceback.format_exc())