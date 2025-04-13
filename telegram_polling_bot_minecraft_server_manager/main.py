# -*- coding: utf-8 -*-
from telegram.ext import ApplicationBuilder
from configmanager.configmanager import ConfigManager
from telegram_polling_bot_minecraft_server_manager.mcbot import MCBot

def main():
    config = ConfigManager().get_config()       
    TOKEN = config["telegram"]["token"]

    app = ( 
    ApplicationBuilder()
    .token(TOKEN)
    .base_url("https://api.telegram.org/bot")
    .build()
    )
    
    MCBot(app, config)

    app.run_polling(poll_interval=2)

if __name__ == "__main__":
    main()
