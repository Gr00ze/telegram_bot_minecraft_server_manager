from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from functools import wraps
import server_manager as server_manager #>:)
from log import * 
from private import TOKEN, user_whitelist, chat_id_whitelist, script_paths

app:Application = None
MAX_MESSAGE_LENGTH:int = 4096



def authorizer(*args, **kwargs):
    decorated_func = message = None
    is_func = callable(args[0])
    if is_func:
        decorated_func = args[0]
    else:
        message = args[0]
    def inner(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            log_update(update)
            user:User = update.effective_user
            if user in user_whitelist and update.effective_chat.id in chat_id_whitelist:
                log(f"User @{user.username} ({user.id}) authorized")
                #return?
                return await func(update, context, *args, **kwargs)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message or "You are not authorized to use this command.")
                log(f"User @{user.username} ({user.id}) not authorized")
        return wrapper
    return inner(decorated_func) if is_func else inner

@authorizer
async def start_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Trying to start 🔄")
    if server_manager.process is not None:
        await context.bot.send_message(update.effective_chat.id, "Server already starting or running ⚠️")
        log(f"Found server starting or running: {server_manager.process} ")
        return
    if server_manager.selected_server is None:
        await context.bot.send_message(update.effective_chat.id, "No server selected\nSelect avaliable server with\n /selectserver")
        log(f"No server selected. Aborted ")
        return
    task = app.create_task(server_manager.server_process_starter())
    if not task:
        await context.bot.send_message(update.effective_chat.id, "Server start failed 💥")
        log(f"Error on starting server")
        return
    await context.bot.send_message(update.effective_chat.id, f"Starting {server_manager.selected_server} 🚀")
    log(f"Server {server_manager.selected_server} starting")

    app.create_task(server_manager.server_output_reader(task))
    log(f"Created task <{server_manager.server_output_reader.__name__}>")

    app.create_task(server_manager.message_listener(context.bot, update.effective_chat.id, "Dedicated server took", "Server started 🟢","RUNNING 🟢"))
    log(f"Created task <{server_manager.message_listener.__name__}>")

@authorizer
async def stop_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Trying to stop 🔄")
    if server_manager.process is None:
        await context.bot.send_message(update.effective_chat.id, "Server already stopped 💤")
        log(f"Server {server_manager.selected_server} already stopped")
        return
    
    app.create_task(server_manager.server_stopper())
    log(f"Created task <{server_manager.server_stopper.__name__}>")

    app.create_task(server_manager.message_listener(context.bot, update.effective_chat.id, "Saving worlds", "Server closing ⬇️", "CLOSING ⬇️"))
    log(f"Created task <{server_manager.message_listener.__name__}>")

    app.create_task(server_manager.message_listener(context.bot, update.effective_chat.id, "Exiting...", "Server closed 💤", "SHUTDOWN 💤"))
    log(f"Created task <{server_manager.message_listener.__name__}>")
   
    

@authorizer
async def status_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(update.effective_chat.id, f"Server {server_manager.selected_server} status: {server_manager.status}" )
    log(f"Sending status to user...")

@authorizer
async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Trying to send 🔄")
    if server_manager.process is None:
        await context.bot.send_message(update.effective_chat.id, "Server offline 💤")
        log(f"User tried to send a command to offline server")
        return
    if len(context.args) == 0:
        await context.bot.send_message(update.effective_chat.id, "No command sent 🤔")
        log(f"User tried to send a command but empty args found")
        return
    command = " ".join(context.args)
    app.create_task(server_manager.server_sender(command))
    log(f"Created task <{server_manager.server_sender.__name__}>")
    await server_manager.asyncio.sleep(3)

    copy_messages = list(server_manager.server_messages)
    date = copy_messages[-1].date
    text = ""
    for msg in copy_messages:
        temp_text = text
        if msg.date != date:
            continue
        temp_text += msg.text + "\n"
        if len(temp_text) >= MAX_MESSAGE_LENGTH:
            await context.bot.send_message(update.effective_chat.id, text)
            text = msg.text + "\n"
        else:
            text = temp_text
    await context.bot.send_message(update.effective_chat.id, text)





#authorizer in send_command
async def player_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.args=["list"]
    await send_command(update, context)


@authorizer("This is a private bot, u cannot use it")
async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(update.effective_chat.id, "Sorry I cannot help you 😎")
    log(f"User asked for help but i wont")

@authorizer
async def select_server(update: Update , context: ContextTypes.DEFAULT_TYPE):
    if server_manager.process:
        await update.effective_message.reply_text("There is already a server up 🤦‍♂️")
        log(f"Server is already up, no selection permitted")
        return
    keyboard:list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(f"{script_name}", callback_data=script_name)] for script_name in script_paths.keys()
    ] 
    keyboard.append([InlineKeyboardButton("Exit",callback_data="Exit")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    log(f"Sending options")
    await context.bot.send_message(update.effective_chat.id,
        f"Server selected: {server_manager.selected_server}\n@{update.effective_user.username} select the server:",reply_markup=reply_markup)


async def selection(update: Update , context: ContextTypes.DEFAULT_TYPE):
    query:CallbackQuery = update.callback_query
    selected:str = query.data
    log(f"Got answer {selected}")
    if selected in script_paths.keys():
        server_manager.selected_server = selected
        log(f"Selection set")
        await query.answer("Done")
        await query.edit_message_text(f"@{query.from_user.username} Selected {selected}.\nTo start the server use\n/startserver ")
        return
    log(f"Invalid answer. Abort")
    await query.answer("No change done")
    await query.edit_message_reply_markup()
    await query.edit_message_text(f"@{query.from_user.username} no change done")
    
async def error_handler(update: Update , context: ContextTypes.DEFAULT_TYPE):
    log(context.error)


def main():
    global app
    app = ( 
    ApplicationBuilder()
    .token(TOKEN)
    .base_url("https://api.telegram.org/bot")
    .build())
    app.add_handler(CommandHandler("startserver", start_server))
    app.add_handler(CommandHandler("stopserver", stop_server))
    app.add_handler(CommandHandler("status", status_server))
    app.add_handler(CommandHandler("sendcommand", send_command))
    app.add_handler(CommandHandler("playeronline", player_online))
    app.add_handler(CommandHandler("help", help_message))
    app.add_handler(CommandHandler("selectserver", select_server))
    app.add_handler(CallbackQueryHandler(selection))
    app.add_error_handler(error_handler)
    log("Running")
    app.run_polling(poll_interval=2)

if __name__ == "__main__":
    main()
