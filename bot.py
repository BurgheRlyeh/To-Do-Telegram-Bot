import copy

import telebot
from telebot import types
from datetime import datetime, timedelta
import threading
import time
from dateutil import relativedelta

bot = telebot.TeleBot('')

users = {}  # словарь для хранения данных пользователей


class Reminder:
    def __init__(self):
        self.text = ''  # текст напоминания
        self.date = None  # дата напоминания
        self.edit = True
        self.files = []  # список прикрепленных файлов
        self.done = False  # флаг выполнения напоминания
        self.delta = None  # флаг повторяющегося напоминания

    def to_string(self):
        return f'{self.text} ({self.date.strftime("%Y-%m-%d %H:%M")}' + \
               (f', every {list(freqs.keys())[list(freqs.values()).index(self.delta)]})' if self.delta else ')')


freqs = {
    'Day': relativedelta.relativedelta(days=1),
    'Week': relativedelta.relativedelta(weeks=1),
    'Month': relativedelta.relativedelta(months=1),
    'Year': relativedelta.relativedelta(years=1)
}


def start(msg):
    chat_id = msg.chat.id
    if chat_id not in users:
        users[chat_id] = []
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
    chat_id = msg.chat.id
    users[chat_id] += [Reminder()]
    enter_text(msg)


def enter_text(msg, rem_idx=-1):
    msg = bot.send_message(msg.chat.id, 'Enter text:')
    bot.register_next_step_handler(msg, process_text_step, rem_idx)


def process_text_step(msg, rem_idx=-1):
    users[msg.chat.id][rem_idx].text = msg.text

    if rem_idx == -1:
        enter_date(msg, rem_idx)
    else:
        start(msg)


def enter_date(msg, rem_idx=-1):
    chat_id = msg.chat.id
    bot.send_message(chat_id, 'Enter the date and time of the reminder\nFormat: YYYY-MM-DD HH:MM\nExample:')
    msg = bot.send_message(chat_id, (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M'))
    bot.register_next_step_handler(msg, process_date_step, rem_idx)


def process_date_step(msg, rem_idx=-1):
    try:
        users[msg.chat.id][rem_idx].date = datetime.strptime(msg.text, '%Y-%m-%d %H:%M')

        if rem_idx == -1:
            want_to(msg, 'Want to attach files to a reminder?', process_files_step)
        else:
            start(msg)

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
    if msg.text == 'Yes':
        send_files(msg)
    else:
        want_to(msg, 'Do you want the reminder to repeat?', process_repeat)


def send_files(msg, rem_idx=-1):
    msg = bot.send_message(msg.chat.id, 'Attach files or press /cancel:')
    bot.register_next_step_handler(msg, process_add_files_step, rem_idx)


def process_add_files_step(msg, rem_idx=-1):
    chat_id = msg.chat.id

    if msg.content_type == 'document':
        file_name = msg.document.file_name

        reminder = users[chat_id][rem_idx]
        reminder.files += [(file_name, msg.document.file_id)]

        bot.send_message(chat_id, f'File {file_name} attached!')
        msg = bot.send_message(chat_id, 'Attach more files or press /cancel:')
        bot.register_next_step_handler(msg, process_add_files_step, rem_idx)

    elif msg.content_type != 'text':
        msg = bot.send_message(chat_id, 'File format is not supported yet\n'
                                        'Try sending through the \"Files\" section or press /cancel')
        bot.register_next_step_handler(msg, process_add_files_step)

    elif rem_idx == -1:
        want_to(msg, 'Do you want the reminder to repeat?', process_repeat)

    else:
        reminder_updated(msg)


def process_repeat(msg, rem_idx=-1):
    if msg.text == 'Yes':
        enter_repeat_period(msg, rem_idx)
    else:
        reminder_created(msg)


def enter_repeat_period(msg, rem_idx=-1):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(
        types.KeyboardButton('Day'),
        types.KeyboardButton('Week'),
        types.KeyboardButton('Month'),
        types.KeyboardButton('Year')
    )
    msg = bot.send_message(msg.chat.id, 'Choose a reminder repeat period:', reply_markup=markup)
    bot.register_next_step_handler(msg, process_repeat_step, rem_idx)


def process_repeat_step(msg, rem_idx=-1):
    if msg.text in freqs:
        users[msg.chat.id][rem_idx].delta = freqs[msg.text]

    if rem_idx != -1:
        reminder_created(msg)
    else:
        start(msg)


def reminder_created(msg):
    bot.send_message(msg.chat.id, 'Reminder created!')
    start(msg)


@bot.message_handler(func=lambda msg: msg.text == 'Current deals')
def current_reminders(msg):
    chat_id = msg.chat.id
    reminders = users.get(chat_id, [])  # получаем список напоминаний пользователя

    if not reminders:
        bot.send_message(chat_id, 'You have no current reminders.')
        start(msg)
        return

    for i, rem in enumerate(reminders):
        if rem.done:
            continue

        markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
        markup.add(
            types.InlineKeyboardButton('Edit', callback_data=f'edit_{i}'),
            types.InlineKeyboardButton('Done', callback_data=f'done_{i}'),
            types.InlineKeyboardButton('Delete', callback_data=f'delete_{i}')
        )
        if rem.delta:
            markup.add(types.InlineKeyboardButton('Delete next only', callback_data=f'delete_next_{i}'))

        bot.send_message(chat_id, rem.to_string(), reply_markup=markup)
        for _, file_id in rem.files:
            bot.send_document(chat_id, file_id)

    start(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_reminder(call):
    chat_id = call.message.chat.id
    rem_idx = int(call.data.split('_')[1])
    rem = users[chat_id][rem_idx]

    bot.send_message(chat_id, rem.to_string())
    for _, file_id in rem.files:
        bot.send_document(chat_id, file_id)

    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(
        types.KeyboardButton('Change text'),
        types.KeyboardButton('Change date'),
        types.KeyboardButton('Change files'),
        types.KeyboardButton('Change repeat period')
    )
    msg = bot.send_message(chat_id, 'Choose an action:', reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_step, rem_idx)


def process_edit_step(msg, rem_idx):
    chat_id = msg.chat.id
    rem = users[chat_id][rem_idx]  # получаем напоминание по индексу
    if msg.text == 'Change text':
        enter_text(msg, rem_idx)
    elif msg.text == 'Change date':
        enter_date(msg, rem_idx)
    elif msg.text == 'Change files':
        for file_name, file_id in rem.files:
            markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
            markup.add(
                types.InlineKeyboardButton('Delete', callback_data=f'delete_file_{rem_idx}_{file_name}')
            )
            bot.send_document(chat_id, file_id, reply_markup=markup)
        send_files(msg, rem_idx)
    elif msg.text == 'Change repeat period':
        enter_repeat_period(msg, rem_idx)


def reminder_updated(msg):
    bot.send_message(msg.chat.id, 'Reminder updated!')
    start(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_file_'))
def delete_file(call):
    data = call.data.split('_')
    rem = users[call.message.chat.id][int(data[2])]
    rem.files = [(name, file_id) for name, file_id in rem.files if name != data[3]]
    bot.answer_callback_query(call.id, text=f'File {data[3]} deleted!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_next_'))
def delete_one_reminder(call):
    rem = users[call.message.chat.id][int(call.data.split('_')[2])]
    rem.date += rem.delta
    bot.answer_callback_query(call.id, text='Next reminder deleted!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_reminder(call):
    users[call.message.chat.id].pop(int(call.data.split('_')[1]))
    bot.answer_callback_query(call.id, text='Reminder deleted!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('done_'))
def done_reminder(call):
    rem = users[call.message.chat.id][int(call.data.split('_')[1])]
    rem.done = True
    bot.answer_callback_query(call.id, text='Reminder done!')
    start(call.message)


@bot.message_handler(func=lambda msg: msg.text == 'Completed deals')
def done_reminders(msg):
    chat_id = msg.chat.id
    rems = users.get(chat_id, [])  # получаем список напоминаний пользователя
    if not rems or not list(filter(lambda r: r.done, rems)):
        bot.send_message(chat_id, 'You have no completed reminders.')
        start(msg)
        return

    for i, rem in enumerate(rems):
        if rem.done:  # выводим только выполненные напоминания
            markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
            markup.add(types.InlineKeyboardButton('Return to current', callback_data=f'undone_{i}'))
            bot.send_message(chat_id, rem.to_string(), reply_markup=markup)

    start(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('undone_'))
def undone_reminder(call):
    users[call.message.chat.id][int(call.data.split('_')[1])].done = False
    bot.answer_callback_query(call.id, text='Reminder returned to current!')
    start(call.message)


def check_reminders():
    while True:
        for chat_id, rems in users.items():
            for i, rem in enumerate(rems):
                if not rem.done and rem.date is not None and rem.date <= datetime.now():
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton('Edit', callback_data=f'edit_{i}'),
                        types.InlineKeyboardButton('Done', callback_data=f'done_{i}')
                    )

                    bot.send_message(chat_id, f'Reminder: {rem.text}', reply_markup=markup)
                    for _, file_id in rem.files:
                        bot.send_document(chat_id, file_id)

                    if rem.delta:
                        users[chat_id] += [copy.deepcopy(rem)]
                        users[chat_id][-1].date += rem.delta
                        rem.date += rem.delta
        time.sleep(10)


if __name__ == '__main__':
    threading.Thread(target=check_reminders).start()
    bot.polling()  # запускаем бота
