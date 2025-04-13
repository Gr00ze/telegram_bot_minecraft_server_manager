import re

class ServerMessage:
    
    def __init__(self, message:str):
        if self.is_valid(message):
            match = re.search(r'\[(.*?)\] \[(.*?)\] \[(.*?)\]: (.*)', message)
            self.date = match.group(1)
            self.type = match.group(2)
            self.from_ = match.group(3)
            self.text = match.group(4)
        else:
            self.date = None
            self.type = None
            self.from_ = None
            self.text = message
        

    def is_valid(self, message:str)-> bool:
        return bool(re.search(r'\[.*\] \[.*\] \[.*\]: .*',message))