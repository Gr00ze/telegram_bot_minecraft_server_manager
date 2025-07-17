from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery,User
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, Application
from functools import wraps


from telegram_polling_bot_minecraft_server_manager.server_manager import ServerStatus
from telegram_polling_bot_minecraft_server_manager.server_message import ServerMessage
from telegram_polling_bot_minecraft_server_manager.server_manager import MCServerManager,asyncio

from telegram_polling_bot_minecraft_server_manager.log import log,log_update


MAX_MESSAGE_LENGTH:int = 4096

class MCBot:
    #Singleton
    _instance = None
    #Type hints
    app: Application
    user_whitelist: list[User]
    chat_id_whitelist: list[int]
    script_paths: dict[str, str]
    server_manager: MCServerManager
    active_tasks: list[asyncio.Task]

    

    def __new__(cls, app, config):
        if cls._instance is None:
            cls._instance = super(MCBot, cls).__new__(cls)
            cls._instance.app = app
            cls._instance.user_whitelist = [
                User(
                    id=user_data["id"],
                    is_bot=user_data["is_bot"],
                    username=user_data.get("username"),
                    first_name=user_data.get("first_name")
                )
                for user_data in config["whitelist"]["users"]
            ]
            cls._instance.chat_id_whitelist = config["whitelist"]["chat_ids"]
            cls._instance.script_paths = config["script_paths"]
            cls._instance.server_manager = MCServerManager(cls._instance.script_paths)
            cls._instance.active_tasks = []
            cls._instance.add_handlers()
            log("MCBot instance created")
        else:
            log("MCBot instance already exists")

        return cls._instance  
    
    @staticmethod
    def authorize(*args, **kwargs):
        decorated_func = message = None
        is_func = callable(args[0])
        if is_func:
            decorated_func = args[0]
        else:
            message = args[0]
        def inner(func):
            @wraps(func)
            async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
                log_update(update)
                user:User = update.effective_user
                if user in MCBot._instance.user_whitelist and update.effective_chat.id in MCBot._instance.chat_id_whitelist:
                    log(f"User @{user.username} ({user.id}) authorized")
                    #return?
                    return await func(self, update, context, *args, **kwargs)
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=message or "You are not authorized to use this command.")
                    log(f"User @{user.username} ({user.id}) not authorized")
            return wrapper
        return inner(decorated_func) if is_func else inner
    

    @authorize
    async def start_server(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text("Trying to start 🔄")
        #precheks
        if self.server_manager is None:
            #It should never happen, but just in case
            log(f"Server Manager is not initialized")
            return
        if self.server_manager.process:
            await context.bot.send_message(update.effective_chat.id, "Server already starting or running ⚠️")
            log(f"Found server starting or running: {self.server_manager.process} ")
            return
        if self.server_manager.selected_server is None:
            await context.bot.send_message(update.effective_chat.id, "No server selected\nSelect avaliable server with\n /selectserver")
            log(f"No server selected. Aborted ")
            return
        #end prechecks
        #close shadow tasks
        self.close_all_tasks()
        #start server
        await context.bot.send_message(update.effective_chat.id, f"Starting {self.server_manager.selected_server} 🚀")
        process = self.server_manager.server_process_starter()
        if (process is None):
            await context.bot.send_message(update.effective_chat.id, "Server start failed 💥\nUnsupported platform")
            log(f"Error on starting server. Unsupported platform")
            return
        
        process_starter_task = self.app.create_task(process)
        log(f"Server {self.server_manager.selected_server} starting")
        if not process_starter_task or process_starter_task is None:
            await context.bot.send_message(update.effective_chat.id, "Server start failed 💥")
            log(f"Error on starting server")
            return
        self.active_tasks.append(process_starter_task)
        
        reader_task = self.app.create_task(self.server_manager.server_output_reader(process_starter_task))
        log(f"Created task <{self.server_manager.server_output_reader.__name__}>")
        self.active_tasks.append(reader_task)

        
        
        
        msg_listener_task1= self.app.create_task(
            self.server_manager.message_listener(
                context.bot,
                update.effective_chat.id,
                "Preparing spawn area:",
                "Opening the world 🌍",
                ServerStatus.WORLD_OPENING
            )
        )
        log(f"Created task <{self.server_manager.message_listener.__name__}> for Almost running")
        self.active_tasks.append(msg_listener_task1)


        async def await_task(): 
        
            await msg_listener_task1  # Attendi che il task1 finisca
            msg_listener_task2 = self.app.create_task(
                self.server_manager.message_listener(
                    context.bot, 
                    update.effective_chat.id, 
                    "Done", 
                    "Server started 🟢",
                    ServerStatus.RUNNING
                )
            )
            log(f"Created task <{self.server_manager.message_listener.__name__}> for RUNNING")
            self.active_tasks.append(msg_listener_task2)
        #this close only if bot task1 and 2 are closed
        self.app.create_task(await_task())

        port_checker_task = self.app.create_task(
            self.server_manager.port_reachable(
            context.bot, 
            update.effective_chat.id, 
            message="Port reachable ➡️🚪🟢"))
        log(f"Created task <{self.server_manager.port_reachable.__name__}> port checking")
        self.active_tasks.append(port_checker_task)
        
    @authorize
    async def stop_server(self,update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text("Trying to stop 🔄")
       
        #close shadow tasks
        self.close_all_tasks()
        
        
        if self.server_manager.process is None:
            await context.bot.send_message(update.effective_chat.id, "Server already stopped 💤")
            log(f"Server {self.server_manager.selected_server} already stopped")
            return
        
        
        await update.effective_message.reply_text("Stopping 🛑")
        #Message listeners for user feedback
        self.app.create_task(self.server_manager.message_listener(context.bot, update.effective_chat.id, "Saving worlds", "Server closing ⬇️", ServerStatus.CLOSING))
        log(f"Created task <{self.server_manager.message_listener.__name__}>")

        self.app.create_task(self.server_manager.message_listener(context.bot, update.effective_chat.id, "Exiting...", "Server closed 💤", ServerStatus.SHUTDOWN))
        log(f"Created task <{self.server_manager.message_listener.__name__}>")
        #Actual action
        close_action_task = self.app.create_task(self.server_manager.server_stopper())
        log(f"Created task <{self.server_manager.server_stopper.__name__}>")
        result = await close_action_task

        if result == 0:
            await context.bot.send_message(update.effective_chat.id, "Server closed 💤")
            self.server_manager.status = ServerStatus.SHUTDOWN
            log(f"Java process exited sucesfully")
            self.close_all_tasks()


        
    
        

    @authorize
    async def status_server(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(update.effective_chat.id, f"Server {self.server_manager.selected_server} status: {self.server_manager.status.value}" )
        log(f"Sending status to user...")

    @authorize
    async def send_command(self,update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text("Trying to send 🔄")
        #server not online
        if self.server_manager.status != ServerStatus.RUNNING:
            await context.bot.send_message(
                update.effective_chat.id, 
                f"The server is {self.server_manager.status.value}.\nYou can send commands only on status {ServerStatus.RUNNING.value}"
                )
            log(f"User tried to send a command to offline server")
            return
        #no command sent
        if len(context.args) == 0:
            await context.bot.send_message(update.effective_chat.id, "No command sent 🤔")
            log(f"User tried to send a command but empty args found")
            return
        
        command:str = " ".join(context.args)
        #send command and receive response
        self.server_manager.reading_new_messages = True

        await self.server_manager.server_sender(command)
        log(f"Created task <{self.server_manager.server_sender.__name__}>")
        new_messages: list[ServerMessage] = []

        try:
            while True:
                # Aspetta una riga nuova con timeout
                msg = await asyncio.wait_for(self.server_manager.message_queue.get(), timeout=3)
                log(f"Got message: {msg.text}", subject=self.send_command.__name__)
                new_messages.append(msg)
        except asyncio.TimeoutError:
            # Timeout: nessun messaggio nuovo entro max_wait secondi
            pass

        self.server_manager.reading_new_messages = False
        
        #handle response data 
        if len(new_messages) == 0:
            await context.bot.send_message(update.effective_chat.id, "No answer sent")
            return
        

        #current_date = new_messages[-1].date
        text:str = ""
        # Combine messages into as few send_message calls as possible, splitting only if too long, but should mantain the for order
        text = ""
        for msg in new_messages:
            # If adding this message would exceed the max length, send what we have so far first
            if len(text) + len(msg.text) + 1 >= MAX_MESSAGE_LENGTH:
                if text.strip():
                    await context.bot.send_message(update.effective_chat.id, text)
                    text = ""
                # If the single message itself is too long, split and send in chunks
            if len(msg.text) >= MAX_MESSAGE_LENGTH:
                for i in range(0, len(msg.text), MAX_MESSAGE_LENGTH):
                    await context.bot.send_message(update.effective_chat.id, msg.text[i:i+MAX_MESSAGE_LENGTH])
            else:
                text += msg.text + "\n"
        if text.strip():
            await context.bot.send_message(update.effective_chat.id, text)
    

    #authorizer in send_command
    async def player_online(self,update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.args=["list"]
        await self.send_command(update, context)


    @authorize
    async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(update.effective_chat.id, "Sorry I cannot help you 😎")
        log(f"User asked for help but i wont")

    @authorize
    async def select_server(self, update: Update , context: ContextTypes.DEFAULT_TYPE):
        if self.server_manager.process:
            await update.effective_message.reply_text("There is already a server up 🤦‍♂️")
            log(f"Server is already up, no selection permitted")
            return
        keyboard:list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(f"{script_name}", callback_data=script_name)] for script_name in self.script_paths.keys()
        ] 
        keyboard.append([InlineKeyboardButton("Exit",callback_data="Exit")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        log(f"Sending options")
        await context.bot.send_message(update.effective_chat.id,
            f"Server selected: {self.server_manager.selected_server}\n@{update.effective_user.username} select the server:",reply_markup=reply_markup)

    @authorize
    async def selection(self,update: Update , context: ContextTypes.DEFAULT_TYPE):
        query:CallbackQuery = update.callback_query
        selected:str = query.data
        log(f"Got answer {selected}")
        if selected in self.script_paths.keys():
            self.server_manager.selected_server = selected
            log(f"Selection set")
            await query.answer("Done")
            await query.edit_message_text(f"@{query.from_user.username} Selected {selected}.\nTo start the server use\n/startserver ")
            return
        log(f"Invalid answer. Abort")
        await query.answer("No change done")
        await query.edit_message_reply_markup()
        await query.edit_message_text(f"@{query.from_user.username} no change done")
       
    async def error_handler(self, update: Update , context: ContextTypes.DEFAULT_TYPE):
        log(context.error)

    def add_handlers(self):
        self.app.add_handler(CommandHandler("startserver", self.start_server))
        self.app.add_handler(CommandHandler("stopserver", self.stop_server))
        self.app.add_handler(CommandHandler("status", self.status_server))
        self.app.add_handler(CommandHandler("sendcommand", self.send_command))
        self.app.add_handler(CommandHandler("playeronline", self.player_online))
        self.app.add_handler(CommandHandler("help", self.help_message))
        self.app.add_handler(CommandHandler("selectserver", self.select_server))
        self.app.add_handler(CallbackQueryHandler(self.selection))
        self.app.add_error_handler(self.error_handler)

    def close_all_tasks(self):
        if self.active_tasks:
            log(f"Cancelling Tasks")
            for task in self.active_tasks:
                log(f"Cancelling task {task}")
                if not task.done():
                    task.cancel()
                    log(f"Task {task} cancelled")
            self.active_tasks.clear()
        
