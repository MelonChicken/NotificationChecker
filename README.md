# NotificationChecker
## Overview
NotificationChecker is a project designed to efficiently monitor and manage notifications. The tool helps users keep track of various notifications from different platforms, ensuring they never miss important updates.

## Features
- Monitor notifications from multiple platforms.
- Filter notifications based on criteria such as urgency, category, or date.
- Automated notification tracking and updates.
  
## Installation
1. Clone the repository:

```bash
git clone https://github.com/MelonChicken/NotificationChecker.git
cd NotificationChecker
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Set up your notification sources in the configuration file (res/config.toml).
```toml

[CLIENT]
URLS = [ "link1",] #put the website that we currently offers 

[CLIENT.NEWEST_POST]
ID = "POST_ID"
DATE = "POST_DATE"

[DISCORD]
TOKEN = "BOT_TOKEN"
GUILD_ID = 0
COMMAND_PREFIX = "!"


[DISCORD.CHANNEL_ID]
MAIN = 0
LOG = 0
```
2. Run the script:
```bash
python notification_checker.py
```

## Contributing
Feel free to fork the project and submit pull requests to contribute to the development of this tool.

License
This project is licensed under the MIT License.

