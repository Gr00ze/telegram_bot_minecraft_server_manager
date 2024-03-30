import platform
import asyncio
import asyncio.subprocess as sp
from telegram import Bot
from private import script_paths
import re
from log import *

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



process: sp.Process = None
status: str = None
last_line : str = None
server_messages : list[ServerMessage] = []
MAX_BUFFER_SIZE : int = 200
selected_server : str = None

#statuses = ["STARTING", "RUNNING", "STOPPING", "CLOSING","SHUTDOWN"]

async def server_process_starter() -> sp.Process:
    global status
    if platform.system() != "Linux":
        log(f"{platform.system()} not supported",subject=server_process_starter.__name__)
        return None
    process = await asyncio.create_subprocess_exec(*["/bin/sh", script_paths[selected_server]], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    return process
    
async def server_output_reader(task:sp.Process):
    global process, last_line, status
    process = await task
    log(f"PID:{process}",subject=server_output_reader.__name__)
    bytes_line:bytes = await process.stdout.readline()
    last_line = bytes_line.decode()
    status = "STARTING 🚀"
    while ("Exiting..." not in last_line):
        bytes_line:bytes = await process.stdout.readline()
        last_line = bytes_line.decode()
        message = ServerMessage(last_line)
        server_messages.append(message)
        if len(server_messages) > MAX_BUFFER_SIZE:
            del server_messages[0]
    
    process.stdin.close()
    process.terminate()
    process = None
    
async def server_stopper():
    global status
    await server_sender("stop")
    status = "STOPPING ⬇️"


async def server_sender(command:str):
    global process
    process.stdin.write(f"{command}\n".encode())

    
async def message_listener(bot:Bot, chat_id:int, server_trigger_message:str, user_custom_reply:str=None, new_status:str = None):
    global status
    log(f"Waiting for: {server_trigger_message}", subject=message_listener.__name__)
    timeout:int = 60 * 20
    sleep_time: int = 0.5
    while timeout > 0:
        await asyncio.sleep(sleep_time)
        timeout -= 1 * sleep_time
        if not last_line or server_trigger_message not in last_line:
            continue
        if new_status:
            status = new_status
        await bot.send_message(chat_id=chat_id, text=user_custom_reply if user_custom_reply else str(last_line))
        break
    
    log(f"Timeout for: {server_trigger_message}", subject=message_listener.__name__)





    