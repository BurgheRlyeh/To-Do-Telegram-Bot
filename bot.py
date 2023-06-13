import copy
import os

import telebot
from telebot import types

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import threading
import time

import pickle
import asyncio

from flask import Flask, request

import gdrive_sync
from config import bot_token

bot = telebot.TeleBot(bot_token)
app = Flask(__name__)

users = {}  # словарь для хранения данных пользователей

service = None
folder_id = None
folder_path = 'users'


class User:
    def __init__(self):
        self.editable = None
        self.current = []
        self.done = []


class Reminder:
    def __init__(self):
        self.text = None  # текст напоминания
        self.date = None  # дата напоминания
        self.files = None  # список прикрепленных файлов
        self.delta = None  # флаг повторяющегося напоминания
        self.notified = None

    def to_string(self):
        return f'{self.text} ({self.date.strftime("%Y-%m-%d %H:%M")}' + \
            (f', every {list(freqs.keys())[list(freqs.values()).index(self.delta)]})' if self.delta else ')')


freqs = {
    'Day': relativedelta(days=1),
    'Week': relativedelta(weeks=1),
    'Month': relativedelta(months=1),
    'Year': relativedelta(years=1)
}


def init_users():
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    file_list = [file for file in os.listdir(folder_path) if file.endswith('.pkl')]

    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)

        with open(file_path, 'rb') as file:
            users[int(os.path.splitext(file_name)[0])] = pickle.load(file)


async def upload_user_data(chat_id):
    file_name = f'{chat_id}.pkl'

    with open(os.path.join(folder_path, file_name), "wb") as file:
        pickle.dump(users[chat_id], file)
    gdrive_sync.upload_file(service, folder_id, folder_path, file_name)


def start(msg):
    chat_id = msg.chat.id
    if chat_id not in users:
        users[chat_id] = User()
    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add(
        types.KeyboardButton('Create a reminder'),
        types.KeyboardButton('Current deals'),
        types.KeyboardButton('Completed deals')
    )
    bot.send_message(chat_id, "Choose an action:", reply_markup=markup)


@bot.message_handler(commands=['start', 'cancel'])
def send_welcome(message):
    start(message)


@bot.message_handler(func=lambda msg: msg.text == 'Create a reminder')
def create_reminder(msg):
    users[msg.chat.id].editable = Reminder()
    enter_text(msg)


def enter_text(msg):
    msg = bot.send_message(msg.chat.id, 'Enter text or press /cancel:')
    bot.register_next_step_handler(msg, process_text_step)


def process_text_step(msg):
    if msg.text == '/cancel':
        users[msg.chat.id].editable = None
        start(msg)
        return

    users[msg.chat.id].editable.text = msg.text

    if users[msg.chat.id].editable.date is None:
        enter_date(msg)
    else:
        reminder_modified(msg)


def enter_date(msg):
    bot.send_message(msg.chat.id, 'Enter the date and time of the reminder or press /cancel\n'
                                  'Format: YYYY-MM-DD HH:MM\n'
                                  'Example:')
    msg = bot.send_message(msg.chat.id, (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M'))
    bot.register_next_step_handler(msg, process_date_step)


def process_date_step(msg):
    if msg.text == '/cancel':
        users[msg.chat.id].editable = None
        start(msg)
        return

    try:
        users[msg.chat.id].editable.date = datetime.strptime(msg.text, '%Y-%m-%d %H:%M')

        if users[msg.chat.id].editable.files is None:
            want_to(msg, 'Want to attach files to a reminder?', process_files_step)
        else:
            reminder_modified(msg)

    except ValueError:
        msg = bot.reply_to(msg, 'Invalid date format. Try again')
        bot.register_next_step_handler(msg, process_date_step)


def want_to(msg, text, next_step):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(
        types.KeyboardButton('Yes'),
        types.KeyboardButton('No')
    )
    msg = bot.send_message(msg.chat.id, text, reply_markup=markup)
    bot.register_next_step_handler(msg, next_step)


def process_files_step(msg):
    users[msg.chat.id].editable.files = []
    if msg.text == 'Yes':
        send_files(msg)
    else:
        want_to(msg, 'Do you want the reminder to repeat?', process_repeat)


def send_files(msg):
    msg = bot.send_message(msg.chat.id, 'Attach file or press /cancel:')
    bot.register_next_step_handler(msg, process_add_files_step)


def process_add_files_step(msg):
    if msg.content_type == 'document':
        users[msg.chat.id].editable.files += [msg.document.file_id]
        bot.send_message(msg.chat.id, f'File {msg.document.file_name} attached!')
        msg = bot.send_message(msg.chat.id, 'Attach one more file or press /cancel:')
        bot.register_next_step_handler(msg, process_add_files_step)

    elif msg.content_type != 'text':
        msg = bot.send_message(msg.chat.id, 'File format is not supported yet\n'
                                            'Try sending through the \"Files\" section or press /cancel')
        bot.register_next_step_handler(msg, process_add_files_step)

    elif users[msg.chat.id].editable.delta is None:
        want_to(msg, 'Do you want the reminder to repeat?', process_repeat)

    else:
        reminder_modified(msg)


def process_repeat(msg):
    users[msg.chat.id].editable.delta = relativedelta()
    if msg.text == 'Yes':
        enter_repeatable(msg)
    else:
        reminder_modified(msg)


def enter_repeatable(msg):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(
        types.KeyboardButton('Day'),
        types.KeyboardButton('Week'),
        types.KeyboardButton('Month'),
        types.KeyboardButton('Year')
    )
    msg = bot.send_message(msg.chat.id, 'Choose a reminder repeat period:', reply_markup=markup)
    bot.register_next_step_handler(msg, process_repeat_step)


def process_repeat_step(msg):
    if msg.text in freqs:
        users[msg.chat.id].editable.delta = freqs[msg.text]

    reminder_modified(msg)


def reminder_modified(msg):
    edit_to_curr(msg.chat.id)
    asyncio.run(upload_user_data(msg.chat.id))
    bot.send_message(msg.chat.id, 'Reminder modified!')
    start(msg)


def edit_to_curr(user_id):
    user = users[user_id]
    user.editable.notified = False
    user.current += [user.editable]
    user.current.sort(key=lambda r: r.date)
    user.editable = None


def edit_to_done(user_id):
    user = users[user_id]
    user.done += [user.editable]
    user.done.sort(key=lambda r: r.date, reverse=True)
    user.editable = None


@bot.message_handler(func=lambda msg: msg.text == 'Current deals')
def current_reminders(msg):
    curr_rems = users[msg.chat.id].current

    if not curr_rems:
        bot.send_message(msg.chat.id, 'You have no current reminders.')

    for i, rem in enumerate(curr_rems):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton('Edit', callback_data=f'edit_{i}'),
            types.InlineKeyboardButton('Done', callback_data=f'done_{i}'),
            types.InlineKeyboardButton('Delete', callback_data=f'delete_{i}')
        )
        if rem.delta != relativedelta():
            markup.add(types.InlineKeyboardButton('Delete next only', callback_data=f'delete_next_{i}'))

        bot.send_message(msg.chat.id, f'{i + 1}. ' + rem.to_string(), reply_markup=markup)
        for file in rem.files:
            bot.send_document(msg.chat.id, file)

    start(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_reminder(call):
    try:
        chat_id = call.message.chat.id

        user = users[chat_id]
        rem = user.editable = user.current.pop(int(call.data.split('_')[1]))

        bot.send_message(chat_id, 'Reminder to edit:')
        bot.send_message(chat_id, rem.to_string())
        for file in rem.files:
            bot.send_document(chat_id, file)

        markup = types.ReplyKeyboardMarkup(row_width=2)
        markup.add(
            types.KeyboardButton('Change text'),
            types.KeyboardButton('Change date'),
            types.KeyboardButton('Change files'),
            types.KeyboardButton('Change repeat period')
        )
        msg = bot.send_message(chat_id, 'Choose an action:', reply_markup=markup)
        bot.register_next_step_handler(msg, process_edit_step)
    except IndexError:
        bot.send_message(call.message.chat.id, 'Error occurred')


def process_edit_step(msg):
    chat_id = msg.chat.id
    rem = users[chat_id].editable  # получаем напоминание по индексу
    if msg.text == 'Change text':
        enter_text(msg)
    elif msg.text == 'Change date':
        enter_date(msg)
    elif msg.text == 'Change files':
        for file in rem.files:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('Delete', callback_data=f'delete_file_{file}'))
            bot.send_document(chat_id, file, reply_markup=markup)
        send_files(msg)
    elif msg.text == 'Change repeat period':
        enter_repeatable(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_file_'))
def delete_file(call):
    try:
        data = call.data.split('_')
        rem = users[call.message.chat.id].editable
        rem.files = [file for file in rem.files if file != data[2]]
        asyncio.run(upload_user_data(call.message.chat.id))
        bot.answer_callback_query(call.id, text=f'File {data[2]} deleted!')
        start(call.message)
    except IndexError:
        bot.send_message(call.message.chat.id, 'Error occurred')


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_next_'))
def delete_next_reminder(call):
    try:
        user = users[call.message.chat.id]
        user.editable = user.current.pop(int(call.data.split('_')[2]))
        user.editable.date += user.editable.delta
        edit_to_curr(call.message.chat.id)
        asyncio.run(upload_user_data(call.message.chat.id))
        bot.answer_callback_query(call.id, text='Next reminder deleted!')
        start(call.message)
    except IndexError:
        bot.send_message(call.message.chat.id, 'Error occurred')


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_reminder(call):
    try:
        users[call.message.chat.id].current.pop(int(call.data.split('_')[1]))
        asyncio.run(upload_user_data(call.message.chat.id))
        bot.answer_callback_query(call.id, text='Reminder deleted!')
        start(call.message)
    except IndexError:
        bot.send_message(call.message.chat.id, 'Error occurred')


@bot.callback_query_handler(func=lambda call: call.data.startswith('done_'))
def done_reminder(call):
    try:
        user = users[call.message.chat.id]
        rem = user.editable = user.current.pop(int(call.data.split('_')[1]))
        edit_to_done(call.message.chat.id)
        # if not rem.notified:
        #     next_to_curr(call.message.chat.id, rem)
        asyncio.run(upload_user_data(call.message.chat.id))
        bot.answer_callback_query(call.id, text='Reminder done!')
        start(call.message)
    except IndexError:
        bot.send_message(call.message.chat.id, 'Error occurred')


def next_to_curr(chat_id, rem):
    user = users[chat_id]
    user.editable = copy.deepcopy(rem)
    user.editable.date += rem.delta
    edit_to_curr(chat_id)


@bot.message_handler(func=lambda msg: msg.text == 'Completed deals')
def done_reminders(msg):
    chat_id = msg.chat.id
    rems = users[chat_id].done

    if not rems:
        bot.send_message(chat_id, 'You have no completed reminders.')

    for i, rem in enumerate(rems):
        markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
        markup.add(types.InlineKeyboardButton('Return to current', callback_data=f'undone_{i}'))
        bot.send_message(chat_id, f'{i + 1}. ' + rem.to_string(), reply_markup=markup)

    start(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('undone_'))
def undone_reminder(call):
    try:
        user = users[call.message.chat.id]
        user.editable = user.done.pop(int(call.data.split('_')[1]))
        edit_to_curr(call.message.chat.id)
        asyncio.run(upload_user_data(call.message.chat.id))
        bot.answer_callback_query(call.id, text='Reminder returned to current!')
        start(call.message)
    except IndexError:
        bot.send_message(call.message.chat.id, 'Error occurred')


def check_reminders():
    for chat_id, user in users.items():
        for i, rem in enumerate(user.current):
            if rem.notified or rem.date > datetime.now():
                continue

            rem.notified = True

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton('Edit', callback_data=f'edit_{i}'),
                types.InlineKeyboardButton('Done', callback_data=f'done_{i}')
            )

            bot.send_message(chat_id, f'Reminder: {rem.text}', reply_markup=markup)
            for file in rem.files:
                bot.send_document(chat_id, file)

            if rem.delta != relativedelta():
                next_to_curr(chat_id, rem)

            asyncio.run(upload_user_data(chat_id))


def inf_checker():
    while True:
        check_reminders()
        time.sleep(60)


@app.route('/')
def http_checker():
    check_reminders()


if __name__ == '__main__':
    service = gdrive_sync.init()
    folder_id = gdrive_sync.get_folder_id(service, 'todo_telegram_bot_users')
    gdrive_sync.download_all_files(service, folder_id, folder_path)

    app.run(port=8000, debug=True)

    init_users()
    threading.Thread(target=inf_checker).start()
    bot.polling()  # запускаем бота
