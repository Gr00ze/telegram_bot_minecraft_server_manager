import telegram as tg
import telegram.ext as tge
from functools import wraps
import server_interaction as server_interaction
from datetime import datetime
from private import TOKEN, user_whitelist, chat_id_whitelist, script_paths

app:tge.Application = None
MAX_MESSAGE_LENGTH:int = 4096



def log_user(update: tg.Update):
    user = update.effective_user
    msg = update.effective_message
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message:str = f"[{current_time}] "
    if user:
        log_message += f" User {user.first_name} @{user.username} ({user.id}) used bot. "
    else:
        print("Uknown User used bot.")
    if msg and msg.text:
        log_message += f"Command: {msg.text}"
    print(log_message)

def authorizer(*args, **kwargs):
    decorated_func = message = None
    is_func = callable(args[0])
    if is_func:
        decorated_func = args[0]
    else:
        message = args[0]
    def inner(func):
        @wraps(func)
        async def wrapper(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            log_user(update)
            if update.message.from_user in user_whitelist and update.message.chat_id in chat_id_whitelist:
                return await func(update, context, *args, **kwargs)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message or "You are not authorized to use this command.")
        return wrapper
    return inner(decorated_func) if is_func else inner

@authorizer
async def start_server(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Trying to start")
    if server_interaction.process is not None:
        await context.bot.send_message(update.effective_chat.id, "Server already running")
        return
    if server_interaction.selected_server is None:
        await context.bot.send_message(update.effective_chat.id, "No server selected")
        return
    task = app.create_task(server_interaction.server_starter())
    print("Task Server Starter Started")
    if not task:
        await context.bot.send_message(update.effective_chat.id, "Server start failed")
        return
    await context.bot.send_message(update.effective_chat.id, f"Starting {server_interaction.selected_server}")
    app.create_task(server_interaction.server_reader(context.bot, update.effective_chat.id, task))
    print("Task Server Viewer Started")

@authorizer
async def stop_server(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Trying to stop")
    if server_interaction.process is None:
        await context.bot.send_message(update.effective_chat.id, "Server already stopped")
        return
    app.create_task(server_interaction.server_stopper())
    print("Task Server Stopper Started")
    

@authorizer
async def status_server(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(update.effective_chat.id, f"Server status: {server_interaction.status} \n >:)" )

@authorizer
async def send_command(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Trying to send")
    if server_interaction.process is None:
        await context.bot.send_message(update.effective_chat.id, "Server offline")
        return
    if len(context.args) == 0:
        await context.bot.send_message(update.effective_chat.id, "No command sent")
        return
    command = " ".join(context.args)
    app.create_task(server_interaction.server_sender(command))
    print("Task Server Sender Started")
    await server_interaction.asyncio.sleep(3)

    #prendo la lista, la inverto (volento potrei scorrere al contrario)
    #salvo la data del primo messaggio
    #prendo tuti i messaggi con la stessa data

 
    copy_messages = list(server_interaction.server_messages)
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
async def player_online(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE):
    context.args=["list"]
    await send_command(update, context)


@authorizer("This is a private bot, u cannot use it")
async def help_message(update: tg.Update, context: tge.ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(update.effective_chat.id, "Sorry I cannot help you")

@authorizer
async def select_server(update: tg.Update , context: tge.ContextTypes.DEFAULT_TYPE):
    if server_interaction.process:
        await update.effective_message.reply_text("There is already a server up")
        return
    keyboard:list[list[tg.InlineKeyboardButton]] = [
        [tg.InlineKeyboardButton(f"{script_name}", callback_data=script_name)] for script_name in script_paths.keys()
    ] 
    keyboard.append([tg.InlineKeyboardButton("Exit",callback_data="Exit")])
    reply_markup = tg.InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(update.effective_chat.id,
        f"Server selected: {server_interaction.selected_server}\n@{update.effective_user.username} select the server:",reply_markup=reply_markup)


async def selection(update: tg.Update , context: tge.ContextTypes.DEFAULT_TYPE):
    query:tg.CallbackQuery = update.callback_query
    selected:str = query.data
    if selected in script_paths.keys():
        server_interaction.selected_server = selected
        await query.answer("Done")
        await query.edit_message_text(f"@{query.from_user.username} Selected {selected}")
        return
    await query.answer("No change done")
    await query.edit_message_reply_markup()
    await query.edit_message_text(f"@{query.from_user.username} no change done")
    



def main():
    global app
    app = ( 
    tge.ApplicationBuilder()
    .token(TOKEN)
    .base_url("https://api.telegram.org/bot")
    .build())
    app.add_handler(tge.CommandHandler("startserver", start_server))
    app.add_handler(tge.CommandHandler("stopserver", stop_server))
    app.add_handler(tge.CommandHandler("status", status_server))
    app.add_handler(tge.CommandHandler("sendcommand", send_command))
    app.add_handler(tge.CommandHandler("playeronline", player_online))
    app.add_handler(tge.CommandHandler("help", help_message))
    app.add_handler(tge.CommandHandler("selectserver", select_server))
    app.add_handler(tge.CallbackQueryHandler(selection))
    print("Running")
    app.run_polling(poll_interval=5)

if __name__ == "__main__":
    main()
