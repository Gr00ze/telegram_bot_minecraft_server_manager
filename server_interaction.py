import platform
import asyncio
import asyncio.subprocess as sp
from telegram import Bot
from private import script_path
import re
class ServerMessage:
    
    def __init__(self, message:str):
        if self.is_valid(message):
            parts = message.split(' ')
            self.date = parts[0]
            self.type = parts[1]
            self.from_ = parts[2]
            self.text = ' '.join(parts[3:])
        else:
            self.date = None
            self.type = None
            self.from_ = None
            self.text = message
        

    def is_valid(self, message:str)-> bool:
        return bool(re.search(r'\[.*\] \[.*\] \[.*\]: .*',message))



process: sp.Process = None
status: str = None
last_line : str = None
server_messages : list[ServerMessage] = []
MAX_SIZE_BUFFER : int = 100





async def server_starter() -> sp.Process:
    global status
    if platform.system() != "Linux":
        return None
    process = await asyncio.create_subprocess_exec(*["/bin/sh", script_path], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    return process
    


async def server_reader(bot:Bot, chat_id:int, task:sp.Process):
    global process, last_line, status
    process = await task
    print(process)
    bytes_line:bytes = await process.stdout.readline()
    status = "STARTING"
    while (True):
        bytes_line:bytes = await process.stdout.readline()
        last_line = bytes_line.decode()
        if "Dedicated server took" in last_line:
            await bot.send_message(chat_id=chat_id, text="Server started")
            status = "RUNNING"
        if "Saving worlds" in last_line:
            await bot.send_message(chat_id=chat_id, text="Server closing")
            status = "CLOSING"

        if "Exiting..." in last_line:
            await bot.send_message(chat_id=chat_id, text="Server closed")
            status = "SHUTDOWN"
            break

        message = ServerMessage(last_line)
        server_messages.append(message)
        if len(server_messages) > MAX_SIZE_BUFFER:
            del server_messages[0]
    
    process.stdin.close()
    process.terminate()
    process = None
    
    

        
async def server_stopper():
    global status
    await server_sender("stop")
    status = "STOPPING"


async def server_sender(command:str):
    global process
    process.stdin.write(f"{command}\n".encode())

    
    




    