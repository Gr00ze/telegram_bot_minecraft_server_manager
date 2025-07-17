import platform
import asyncio
import asyncio.subprocess as asp
import socket

from telegram import Bot

from telegram_polling_bot_minecraft_server_manager.server_message import ServerMessage
from telegram_polling_bot_minecraft_server_manager.log import log

#TODO class enumeratorstate
from enum import Enum

class ServerStatus(str, Enum):
    STARTING = "STARTING 🚀"
    RUNNING = "RUNNING 🟢"
    STOPPING = "STOPPING ⬇️"
    CLOSING = "CLOSING ⬇️"
    SHUTDOWN = "SHUTDOWN 💤"
    WORLD_OPENING = "WORLD OPENING 🌍"


MAX_BUFFER_SIZE : int = 200

class MCServerManager:
    selected_server:str
    
    
    def __init__(self, script_paths):
        self.process: asp.Process = None
        self.status: ServerStatus = ServerStatus.SHUTDOWN
        self.last_line:str = None
        self.server_messages:list[ServerMessage] = []   
        self.message_queue:asyncio.Queue[ServerMessage] = asyncio.Queue() 
        self.reading_new_messages: bool = False    
        self.selected_server:str = None
        self.script_paths:list[str] = script_paths
    
    async def server_process_starter(self) -> asp.Process:
    
        if platform.system() != "Linux":
            log(f"{platform.system()} not supported",subject=self.server_process_starter.__name__)
            return None
        self.process = await asyncio.create_subprocess_exec(
            *["/bin/sh", self.script_paths[self.selected_server]],
              stdin=asp.PIPE, stdout=asp.PIPE)
        return self.process
    
    async def server_output_reader(self, task:asp.Process):
        self.process = await task
        log(f"PID:{self.process}",subject=self.server_output_reader.__name__)
        self.status = ServerStatus.STARTING
        self.server_messages.clear()
        self.last_line = None

        bytes_line:bytes = await self.process.stdout.readline()
        self.last_line = bytes_line.decode()
        running = True
        while (running):
            
            bytes_line:bytes = await self.process.stdout.readline()
            self.last_line = bytes_line.decode()
            #log(f"Writing lastline :{last_line}",subject=server_output_reader.__name__) 
            message = ServerMessage(self.last_line)
            self.server_messages.append(message)
            if self.reading_new_messages:
                await self.message_queue.put(message)

            if len(self.server_messages) > MAX_BUFFER_SIZE:
                del self.server_messages[0]
            if("Exiting..." in self.last_line):
                break
        log(f"Task closing",subject=self.server_output_reader.__name__)   
        
        
    async def server_stopper(self):
        await self.server_sender("stop")
        self.status = ServerStatus.STOPPING
        self.process.stdin.close()
        await self.process.wait()

        if self.process.returncode == 0:
            log(f"Server stopped successfully",subject=self.server_stopper.__name__)
            self.process = None
            return 0
        
        log(f"Server stopped with error code: {self.process.returncode}",subject=self.server_stopper.__name__)
        self.process = None
        return 1


    async def server_sender(self,command:str):
        self.process.stdin.write(f"{command}\n".encode())

    
    async def message_listener(self, bot:Bot, chat_id:int, server_trigger_message:str, user_custom_reply:str=None, new_status:str = None):
        """
        Listen for a specific message from the server and send a reply to the user.
        :param bot: The Telegram bot instance.
        :param chat_id: The chat ID to send the message to.
        :param server_trigger_message: The message to listen for from the server.
        :param user_custom_reply: The custom reply to send to the user. If None, the last line from the server will be sent.
        :param new_status: The new status to set if the server_trigger_message is found.
        :return: None  
        """
        log(f"Waiting for: {server_trigger_message}", subject=self.message_listener.__name__)
        timeout:int = 60 * 5
        sleep_time: int = 0.2
        while timeout > 0:
            await asyncio.sleep(sleep_time)
            timeout -= 1 * sleep_time
            
            for message in self.server_messages:
                if server_trigger_message in message.text:
                    log(f"Found on server messages list: {server_trigger_message}", subject=self.message_listener.__name__)    
                    if new_status:
                        self.status = new_status
                    try:
                        await bot.send_message(chat_id=chat_id, text=user_custom_reply if user_custom_reply else str(self.last_line))
                    except Exception as e:
                        log(f"Error sending message: {e}", subject=self.message_listener.__name__)
            
                    return

            #log(f"Reading lastline {last_line}", subject=message_listener.__name__)
            if not self.last_line or server_trigger_message not in self.last_line:
                continue
            
            if new_status:
                self.status = new_status
            try:
                await bot.send_message(chat_id=chat_id, text=user_custom_reply if user_custom_reply else str(self.last_line))
            except Exception as e:
                log(f"Error sending message: {e}", subject=self.message_listener.__name__)
            
            return
            
        log(f"Timeout for: {server_trigger_message}", subject=self.message_listener.__name__)

    async def port_reachable(self, bot: Bot, chat_id: int, host='127.0.0.1', port=25565, message="Port reachable ➡️🚪🟢"):
        try:
            while True:
                if asyncio.current_task().cancelled():
                    log("Task cancelled. Stopping port check.", subject=self.port_reachable.__name__)
                    break
                await asyncio.sleep(10)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    result = s.connect_ex((host, port))
                    if result == 0:
                        log(f"Port {port} reachable. Sending Update...", subject=self.port_reachable.__name__)
                        await bot.send_message(chat_id=chat_id, text=message)
                        return  # esce dal loop → task chiuso
                    log(f"Port {port} is still unreachable", subject=self.port_reachable.__name__)
        except Exception as e:
            log(f"Task closed with error: {e}", subject=self.port_reachable.__name__)









    