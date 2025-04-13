import json
import os
import sys

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_or_generate_config()

    def load_or_generate_config(self):
        if not os.path.exists(self.config_file):
            print(f"Errore: il file {self.config_file} non esiste.")
            self._generate_config()
            sys.exit(1) 
        else:
            with open(self.config_file, 'r') as file:
                return json.load(file)
            
    def _generate_config(self):
        default_config = {
            "telegram": {
                "token": "YOUR_BOT_TOKEN",  
                "webhook_url": "https://yourdomain.com/webhook"
            },
            "rcon": {
                "host": "127.0.0.1",
                "port": 25575,
                "password": "YOUR_RCON_PASSWORD"
            },
            "whitelist": {
                "users": [ {"id":123456,"is_bot":False,"username":"username","first_name":"can be empty"}],       # Lista di utenti (User)
                "chat_ids": [123456,123457]    
            },
            "script_paths": {"server_name":"server_path"}   
        }

        with open(self.config_file, 'w') as file:
            json.dump(default_config, file, indent=4)

        print(f"File {self.config_file} created with default configuration.")
        print("Please, edit the file before restart the program.")
    
    def get_config(self):
        return self.config
    
    