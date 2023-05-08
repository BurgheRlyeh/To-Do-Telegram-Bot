import copy

import telebot
from telebot import types
from datetime import datetime, timedelta
import threading
import time
from dateutil.relativedelta import relativedelta

bot = telebot.TeleBot('6222852548:AAGkFKtoKUw0svkNH5AKMEYiVmnxrj24zFg')

users = {}  # словарь для хранения данных пользователей


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

    def to_string(self):
        return f'{self.text} ({self.date.strftime("%Y-%m-%d %H:%M")}' + \
            (f', every {list(freqs.keys())[list(freqs.values()).index(self.delta)]})' if self.delta else ')')


freqs = {
    'Day': relativedelta(days=1),
    'Week': relativedelta(weeks=1),
    'Month': relativedelta(months=1),
    'Year': relativedelta(years=1)
}


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
        users[msg.chat.id].editable.files += [(msg.document.file_name, msg.document.file_id)]
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
    bot.send_message(msg.chat.id, 'Reminder modified!')
    start(msg)


def edit_to_curr(user_id):
    user = users[user_id]
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
        for _, file_id in rem.files:
            bot.send_document(msg.chat.id, file_id)

    start(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_reminder(call):
    chat_id = call.message.chat.id
    user = users[chat_id]
    rem = user.editable = user.current.pop(int(call.data.split('_')[1]))

    bot.send_message(chat_id, 'Reminder to edit:')
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
    bot.register_next_step_handler(msg, process_edit_step)


def process_edit_step(msg):
    chat_id = msg.chat.id
    rem = users[chat_id].editable  # получаем напоминание по индексу
    if msg.text == 'Change text':
        enter_text(msg)
    elif msg.text == 'Change date':
        enter_date(msg)
    elif msg.text == 'Change files':
        for file_name, file_id in rem.files:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('Delete', callback_data=f'delete_file_{file_name}'))
            bot.send_document(chat_id, file_id, reply_markup=markup)
        send_files(msg)
    elif msg.text == 'Change repeat period':
        enter_repeatable(msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_file_'))
def delete_file(call):
    data = call.data.split('_')
    rem = users[call.message.chat.id].editable
    rem.files = [(name, file_id) for name, file_id in rem.files if name != data[2]]
    bot.answer_callback_query(call.id, text=f'File {data[2]} deleted!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_next_'))
def delete_next_reminder(call):
    user = users[call.message.chat.id]
    user.editable = user.current.pop(int(call.data.split('_')[2]))
    user.editable.date += user.editable.delta
    edit_to_curr(call.message.chat.id)
    bot.answer_callback_query(call.id, text='Next reminder deleted!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_reminder(call):
    users[call.message.chat.id].current.pop(int(call.data.split('_')[1]))
    bot.answer_callback_query(call.id, text='Reminder deleted!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('done_'))
def done_reminder(call):
    user = users[call.message.chat.id]
    user.editable = user.current.pop(int(call.data.split('_')[1]))
    edit_to_done(call.message.chat.id)
    bot.answer_callback_query(call.id, text='Reminder done!')
    start(call.message)


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
    user = users[call.message.chat.id]
    user.editable = user.done.pop(int(call.data.split('_')[1]))
    edit_to_curr(call.message.chat.id)
    bot.answer_callback_query(call.id, text='Reminder returned to current!')
    start(call.message)


def check_reminders():
    while True:
        for chat_id, user in users.items():
            for i, rem in enumerate(user.current):
                if rem.date == datetime.now().replace(second=0, microsecond=0):
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton('Edit', callback_data=f'edit_{i}'),
                        types.InlineKeyboardButton('Done', callback_data=f'done_{i}')
                    )

                    bot.send_message(chat_id, f'Reminder: {rem.text}', reply_markup=markup)
                    for _, file_id in rem.files:
                        bot.send_document(chat_id, file_id)

                    if rem.delta != relativedelta():
                        user.editable = copy.deepcopy(rem)
                        user.editable += rem.delta
                        edit_to_curr(chat_id)
        time.sleep(60)


if __name__ == '__main__':
    threading.Thread(target=check_reminders).start()
    bot.polling()  # запускаем бота
