import telebot
from telebot import types
import datetime
import threading
import time

bot = telebot.TeleBot('')  # замените YOUR_TOKEN_HERE на токен вашего бота

commands = [
    {'command': 'start', 'description': 'Начать работу с ботом'},
    {'command': 'cancel', 'description': 'Отменить текущую операцию'}
]

users = {}  # словарь для хранения данных пользователей


class Reminder:
    def __init__(self):
        self.text = ''  # текст напоминания
        self.date = None  # дата напоминания
        self.files = []  # список прикрепленных файлов
        self.done = False  # флаг выполнения напоминания
        self.repeat = False  # флаг повторяющегося напоминания


def start(message):
    chat_id = message.chat.id
    if chat_id not in users:
        users[chat_id] = []  # создаем пустой список напоминаний для нового пользователя
    markup = types.ReplyKeyboardMarkup(row_width=1)  # создаем клавиатуру с выбором действий
    markup.add(
        types.KeyboardButton('Создать напоминание'),
        types.KeyboardButton('Текущие дела'),
        types.KeyboardButton('Выполненные дела')
    )
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    start(message)  # выводим клавиатуру с выбором действий при старте бота


@bot.message_handler(func=lambda message: message.text == 'Создать напоминание')
def create_reminder(message):
    chat_id = message.chat.id
    reminder = Reminder()  # создаем новое напоминание
    users[chat_id].append(reminder)  # добавляем его в список напоминаний пользователя
    msg = bot.send_message(chat_id, 'Введите текст напоминания:')
    bot.register_next_step_handler(msg, process_text_step)  # переходим к следующему шагу


def process_text_step(message):
    chat_id = message.chat.id
    users[chat_id][-1].text = message.text

    bot.send_message(chat_id, 'Введите дату и время напоминания\nФормат: ГГГГ-ММ-ДД ЧЧ:ММ\nПример:')
    next_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
    msg = bot.send_message(chat_id, next_date)
    bot.register_next_step_handler(msg, process_date_step)


def process_date_step(message):
    chat_id = message.chat.id
    try:
        date_str = message.text  # получаем дату от пользователя
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')  # преобразуем строку в объект datetime
        users[chat_id][-1].date = date  # сохраняем дату в напоминании
        markup = types.ReplyKeyboardMarkup(row_width=2)  # создаем клавиатуру с выбором действий
        markup.add(
            types.KeyboardButton('Да'),
            types.KeyboardButton('Нет')
        )
        msg = bot.send_message(chat_id, 'Хотите прикрепить файлы к напоминанию?', reply_markup=markup)
        bot.register_next_step_handler(msg, process_files_step)  # переходим к следующему шагу
    except ValueError:
        msg = bot.reply_to(message, 'Неверный формат даты. Попробуйте еще раз.')
        bot.register_next_step_handler(msg, process_date_step)  # повторяем шаг


def process_files_step(message):
    chat_id = message.chat.id
    if message.text == 'Да':
        msg = bot.send_message(chat_id, 'Прикрепите файлы:')
        bot.register_next_step_handler(msg, process_add_files_step)
    else:
        reminder_created(message)


def process_add_files_step(message):
    chat_id = message.chat.id
    reminder = users[chat_id][-1]

    if message.content_type == 'document':
        file_id = message.document.file_id
        file_name = message.document.file_name
        reminder.files.append((file_name, file_id))
    else:
        msg = bot.send_message(chat_id, 'К сожалению, данный формат файлов пока не поддерживается. '
                                        'Попробуйте отправить документ через раздел \"Файлы\"')
        bot.register_next_step_handler(msg, process_add_files_step)


@bot.message_handler(content_types=['document'])
def handle_docs_photo(message):
    chat_id = message.chat.id
    file_id = message.document.file_id
    file_name = message.document.file_name
    bot.send_message(chat_id, f'Файл {file_name} получен!')


def reminder_created(message):
    chat_id = message.chat.id
    reminder = users[chat_id][-1]  # получаем последнее созданное напоминание
    bot.send_message(chat_id, 'Напоминание создано!')
    start(message)  # выводим клавиатуру с выбором действий


@bot.message_handler(func=lambda message: message.text == 'Текущие дела')
def current_reminders(message):
    chat_id = message.chat.id
    reminders = users.get(chat_id, [])  # получаем список напоминаний пользователя
    if not reminders:
        bot.send_message(chat_id, 'У вас нет текущих напоминаний.')
        start(message)
        return
    for i, reminder in enumerate(reminders):
        if not reminder.done:  # выводим только невыполненные напоминания
            text = f'{i + 1}. {reminder.text} ({reminder.date.strftime("%Y-%m-%d %H:%M")})'
            bot.send_message(chat_id, text)
            markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
            markup.add(
                types.InlineKeyboardButton('Редактировать', callback_data=f'edit_{i}'),
                types.InlineKeyboardButton('Удалить', callback_data=f'delete_{i}'),
                types.InlineKeyboardButton('Выполнено', callback_data=f'done_{i}')
            )
            bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)
    start(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_reminder(call):
    chat_id = call.message.chat.id
    reminder_index = int(call.data.split('_')[1])  # получаем индекс напоминания из данных callback
    reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
    bot.send_message(chat_id, f'Текст: {reminder.text}')
    bot.send_message(chat_id, f'Дата: {reminder.date.strftime("%Y-%m-%d %H:%M")}')
    if reminder.files:
        bot.send_message(chat_id, 'Файлы:')
        for file_name, file_id in reminder.files:
            bot.send_document(chat_id, file_id, caption=file_name)
    else:
        bot.send_message(chat_id, 'Файлы отсутствуют')
    markup = types.ReplyKeyboardMarkup(row_width=2)  # создаем клавиатуру с выбором действий
    markup.add(
        types.KeyboardButton('Изменить текст'),
        types.KeyboardButton('Изменить дату'),
        types.KeyboardButton('Изменить файлы')
    )
    msg = bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)
    bot.register_next_step_handler(msg, process_edit_step, reminder_index)  # переходим к следующему шагу


def process_edit_step(message, reminder_index):
    chat_id = message.chat.id
    reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
    if message.text == 'Изменить текст':
        msg = bot.send_message(chat_id, 'Введите новый текст:')
        bot.register_next_step_handler(msg, process_edit_text_step, reminder_index)  # переходим к следующему шагу
    elif message.text == 'Изменить дату':
        bot.send_message(chat_id, 'Введите новую дату и время:')
        bot.send_message(chat_id, 'Формат: ГГГГ-ММ-ДД ЧЧ:ММ')
        msg = bot.send_message(chat_id, 'Например: 2023-04-22 14:30')
        bot.register_next_step_handler(msg, process_edit_date_step, reminder_index)  # переходим к следующему шагу
    elif message.text == 'Изменить файлы':
        if reminder.files:
            for file_name, file_id in reminder.files:
                markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
                markup.add(
                    types.InlineKeyboardButton('Удалить', callback_data=f'delete_file_{reminder_index}_{file_name}')
                )
                bot.send_document(chat_id, file_id, caption=file_name, reply_markup=markup)
        msg = bot.send_message(chat_id, 'Прикрепите новые файлы или нажмите /cancel для отмены:')
        bot.register_next_step_handler(msg, process_edit_files_step, reminder_index)  # переходим к следующему шагу


def process_edit_text_step(message, reminder_index):
    chat_id = message.chat.id
    text = message.text  # получаем новый текст от пользователя
    reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
    reminder.text = text  # сохраняем новый текст в напоминании
    bot.send_message(chat_id, 'Текст изменен!')
    start(message)  # выводим клавиатуру с выбором действий


def process_edit_date_step(message, reminder_index):
    chat_id = message.chat.id
    date_str = message.text  # получаем новую дату от пользователя
    try:
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')  # преобразуем строку в объект datetime
        reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
        reminder.date = date  # сохраняем новую дату в напоминании
        bot.send_message(chat_id, 'Дата изменена!')
        start(message)  # выводим клавиатуру с выбором действий
    except ValueError:
        msg = bot.reply_to(message, 'Неверный формат даты. Попробуйте еще раз.')
        bot.register_next_step_handler(msg,
                                       process_edit_date_step,
                                       reminder_index)  # повторяем шаг


def process_edit_files_step(message, reminder_index):
    chat_id = message.chat.id
    if message.content_type == 'document':
        file_id = message.document.file_id
        file_name = message.document.file_name

        reminder = users[chat_id][reminder_index]
        reminder.files.append((file_name, file_id))
        bot.send_message(chat_id, f'Файл {file_name} добавлен!')
        msg = bot.send_message(chat_id,
                               'Прикрепите еще файлы или нажмите /cancel для отмены:')
        bot.register_next_step_handler(msg,
                                       process_edit_files_step,
                                       reminder_index)
    else:
        start(message)


@bot.message_handler(commands=['cancel'])
def cancel(message):
    start(message)  # выводим клавиатуру с выбором действий при отмене


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_file_'))
def delete_file(call):
    chat_id = call.message.chat.id
    data = call.data.split('_')
    reminder_index = int(data[2])  # получаем индекс напоминания из данных callback
    file_name = data[3]  # получаем имя файла из данных callback
    reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
    reminder.files = [(name, file_id) for name, file_id in reminder.files if
                      name != file_name]  # удаляем файл из списка файлов напоминания
    bot.answer_callback_query(call.id, text=f'Файл {file_name} удален!')
    start(call.message)  # выводим клавиатуру с выбором действий


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_reminder(call):
    chat_id = call.message.chat.id
    reminder_index = int(call.data.split('_')[1])  # получаем индекс напоминания из данных callback
    users[chat_id].pop(reminder_index)  # удаляем напоминание из списка напоминаний пользователя
    bot.answer_callback_query(call.id, text='Напоминание удалено!')
    start(call.message)  # выводим клавиатуру с выбором действий


@bot.callback_query_handler(func=lambda call: call.data.startswith('done_'))
def done_reminder(call):
    chat_id = call.message.chat.id
    reminder_index = int(call.data.split('_')[1])  # получаем индекс напоминания из данных callback
    reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
    reminder.done = True  # помечаем напоминание как выполненное
    bot.answer_callback_query(call.id, text='Напоминание выполнено!')
    start(call.message)  # выводим клавиатуру с выбором действий


@bot.message_handler(func=lambda message: message.text == 'Выполненные дела')
def done_reminders(message):
    chat_id = message.chat.id
    reminders = users.get(chat_id, [])  # получаем список напоминаний пользователя
    if not reminders:
        bot.send_message(chat_id, 'У вас нет выполненных напоминаний.')
        start(message)
        return
    for i, reminder in enumerate(reminders):
        if reminder.done:  # выводим только выполненные напоминания
            text = f'{i + 1}. {reminder.text} ({reminder.date.strftime("%Y-%m-%d %H:%M")})'
            bot.send_message(chat_id, text)
            markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
            btn1 = types.InlineKeyboardButton('Вернуть в текущие', callback_data=f'undone_{i}')
            markup.add(btn1)
            bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)
    start(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('undone_'))
def undone_reminder(call):
    chat_id = call.message.chat.id
    reminder_index = int(call.data.split('_')[1])  # получаем индекс напоминания из данных callback
    reminder = users[chat_id][reminder_index]  # получаем напоминание по индексу
    reminder.done = False  # помечаем напоминание как невыполненное
    bot.answer_callback_query(call.id, text='Напоминание возвращено в текущие!')
    start(call.message)  # выводим клавиатуру с выбором действий


def check_reminders():
    while True:
        current_time = datetime.datetime.now()
        for chat_id, reminders in users.items():
            for reminder in reminders:
                if not reminder.done and reminder.date is not None and reminder.date <= current_time:
                    bot.send_message(chat_id, f'Напоминание: {reminder.text}')
                    reminder.done = True
        time.sleep(10)  # проверяем напоминания каждую минуту


if __name__ == '__main__':
    threading.Thread(target=check_reminders).start()
    bot.set_my_commands([
        {
            'command': 'start',
            'description': 'Начать работу с ботом'
        },
        {
            'command': 'cancel',
            'description': 'Отменить текущую операцию'
        }
    ])
    bot.polling()  # запускаем бота

# import telebot
# from telebot import types
# import datetime
#
# bot = telebot.TeleBot('6222852548:AAGkFKtoKUw0svkNH5AKMEYiVmnxrj24zFg')
#
# users = {}
#
#
# class Reminder:
#     def __init__(self):
#         self.text = ''
#         self.date = None
#         self.files = []
#         self.done = False
#
#
# def start(message):
#     chat_id = message.chat.id
#     if chat_id not in users:
#         users[chat_id] = []
#     markup = types.ReplyKeyboardMarkup(row_width=2)
#     itembtn1 = types.KeyboardButton('Создать напоминание')
#     itembtn2 = types.KeyboardButton('Текущие дела')
#     itembtn3 = types.KeyboardButton('Выполненные дела')
#     markup.add(itembtn1, itembtn2, itembtn3)
#     bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)
#
#
# @bot.message_handler(commands=['start'])
# def send_welcome(message):
#     start(message)
#
#
# @bot.message_handler(func=lambda message: message.text == 'Создать напоминание')
# def create_reminder(message):
#     chat_id = message.chat.id
#     reminder = Reminder()
#     users[chat_id].append(reminder)
#     msg = bot.send_message(chat_id, 'Введите текст напоминания:')
#     bot.register_next_step_handler(msg, process_text_step)
#
#
# def process_text_step(message):
#     chat_id = message.chat.id
#     text = message.text
#     reminder = users[chat_id][-1]
#     reminder.text = text
#     bot.send_message(chat_id, 'Выберите дату и время напоминания:')
#     bot.send_message(chat_id, 'Формат: ГГГГ-ММ-ДД ЧЧ:ММ')
#     msg = bot.send_message(chat_id, 'Например: 2023-04-22 14:30')
#     bot.register_next_step_handler(msg, process_date_step)
#
#
# def process_date_step(message):
#     chat_id = message.chat.id
#     date_str = message.text
#     try:
#         date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')
#         reminder = users[chat_id][-1]
#         reminder.date = date
#         markup = types.ReplyKeyboardMarkup(row_width=2)
#         itembtn1 = types.KeyboardButton('Да')
#         itembtn2 = types.KeyboardButton('Нет')
#         markup.add(itembtn1, itembtn2)
#         msg = bot.send_message(chat_id, 'Хотите прикрепить файлы к напоминанию?', reply_markup=markup)
#         bot.register_next_step_handler(msg, process_files_step)
#     except ValueError:
#         msg = bot.reply_to(message, 'Неверный формат даты. Попробуйте еще раз.')
#         bot.register_next_step_handler(msg, process_date_step)
#
#
# def process_files_step(message):
#     chat_id = message.chat.id
#     if message.text == 'Да':
#         msg = bot.send_message(chat_id, 'Прикрепите файлы:')
#         bot.register_next_step_handler(msg, process_add_files_step)
#     else:
#         reminder_created(message)
#
#
# def process_add_files_step(message):
#     chat_id = message.chat.id
#     file_id = message.document.file_id
#     file_name = message.document.file_name
#     reminder = users[chat_id][-1]
#     reminder.files.append((file_name, file_id))
#
#
# @bot.message_handler(content_types=['document'])
# def handle_docs_photo(message):
#     chat_id = message.chat.id
#     file_id = message.document.file_id
#     file_name = message.document.file_name
#     bot.send_message(chat_id, f'Файл {file_name} получен!')
#
#
#
# def reminder_created(message):
#     chat_id = message.chat.id
#     reminder = users[chat_id][-1]
#     bot.send_message(chat_id, 'Напоминание создано!')
#     start(message)
#
# @bot.message_handler(func=lambda message: message.text == 'Текущие дела')
# def current_reminders(message):
#     chat_id = message.chat.id
#     reminders = users.get(chat_id, [])
#     if not reminders:
#         bot.send_message(chat_id, 'У вас нет текущих напоминаний.')
#         start(message)
#         return
#     for i, reminder in enumerate(reminders):
#         if not reminder.done:
#             text = f'{i+1}. {reminder.text} ({reminder.date.strftime("%Y-%m-%d %H:%M")})'
#             bot.send_message(chat_id, text)
#             markup = types.InlineKeyboardMarkup()
#             btn1 = types.InlineKeyboardButton('Редактировать', callback_data=f'edit_{i}')
#             btn2 = types.InlineKeyboardButton('Удалить', callback_data=f'delete_{i}')
#             btn3 = types.InlineKeyboardButton('Выполнено', callback_data=f'done_{i}')
#             markup.add(btn1, btn2, btn3)
#             bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)
#     start(message)
#
# @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
# def edit_reminder(call):
#     chat_id = call.message.chat.id
#     reminder_index = int(call.data.split('_')[1])
#     reminder = users[chat_id][reminder_index]
#     bot.send_message(chat_id, f'Текст: {reminder.text}')
#     bot.send_message(chat_id, f'Дата: {reminder.date.strftime("%Y-%m-%d %H:%M")}')
#     if reminder.files:
#         bot.send_message(chat_id, 'Файлы:')
#         for file_name, file_id in reminder.files:
#             bot.send_document(chat_id, file_id, caption=file_name)
#     else:
#         bot.send_message(chat_id, 'Файлы отсутствуют')
#     markup = types.ReplyKeyboardMarkup(row_width=2)
#     itembtn1 = types.KeyboardButton('Изменить текст')
#     itembtn2 = types.KeyboardButton('Изменить дату')
#     itembtn3 = types.KeyboardButton('Изменить файлы')
#     markup.add(itembtn1, itembtn2, itembtn3)
#     msg = bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)
#     bot.register_next_step_handler(msg, process_edit_step, reminder_index)
#
# def process_edit_step(message, reminder_index):
#     chat_id = message.chat.id
#     reminder = users[chat_id][reminder_index]
#     if message.text == 'Изменить текст':
#         msg = bot.send_message(chat_id, 'Введите новый текст:')
#         bot.register_next_step_handler(msg, process_edit_text_step, reminder_index)
#     elif message.text == 'Изменить дату':
#         bot.send_message(chat_id, 'Введите новую дату и время:')
#         bot.send_message(chat_id, 'Формат: ГГГГ-ММ-ДД ЧЧ:ММ')
#         msg = bot.send_message(chat_id, 'Например: 2023-04-22 14:30')
#         bot.register_next_step_handler(msg, process_edit_date_step, reminder_index)
#     elif message.text == 'Изменить файлы':
#         if reminder.files:
#             for file_name, file_id in reminder.files:
#                 markup = types.InlineKeyboardMarkup()
#                 btn1 = types.InlineKeyboardButton('Удалить', callback_data=f'delete_file_{reminder_index}_{file_name}')
#                 markup.add(btn1)
#                 bot.send_document(chat_id, file_id, caption=file_name,
#                                   reply_markup=markup)
#         msg = bot.send_message(chat_id,
#                                'Прикрепите новые файлы или нажмите /cancel для отмены:')
#         bot.register_next_step_handler(msg,
#                                        process_edit_files_step,
#                                        reminder_index)
#
# def process_edit_text_step(message, reminder_index):
#     chat_id = message.chat.id
#     text = message.text
#     reminder = users[chat_id][reminder_index]
#     reminder.text = text
#     bot.send_message(chat_id, 'Текст изменен!')
#     start(message)
#
# def process_edit_date_step(message, reminder_index):
#     chat_id = message.chat.id
#     date_str = message.text
#     try:
#         date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')
#         reminder = users[chat_id][reminder_index]
#         reminder.date = date
#         bot.send_message(chat_id, 'Дата изменена!')
#         start(message)
#     except ValueError:
#         msg = bot.reply_to(message, 'Неверный формат даты. Попробуйте еще раз.')
#         bot.register_next_step_handler(msg,
#                                        process_edit_date_step,
#                                        reminder_index)
#
# def process_edit_files_step(message, reminder_index):
#     chat_id = message.chat.id
#     if message.content_type == 'document':
#         file_id = message.document.file_id
#         file_name = message.document.file_name
#         reminder = users[chat_id][reminder_index]
#         reminder.files.append((file_name, file_id))
#         bot.send_message(chat_id, f'Файл {file_name} добавлен!')
#         msg = bot.send_message(chat_id,
#                                'Прикрепите еще файлы или нажмите /cancel для отмены:')
#         bot.register_next_step_handler(msg,
#                                        process_edit_files_step,
#                                        reminder_index)
#     else:
#         start(message)
#
# @bot.message_handler(commands=['cancel'])
# def cancel(message):
#     start(message)
#
# @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_file_'))
# def delete_file(call):
#     chat_id = call.message.chat.id
#     data = call.data.split('_')
#     reminder_index = int(data[2])
#     file_name = data[3]
#     reminder = users[chat_id][reminder_index]
#     reminder.files = [(name, file_id) for name, file_id in reminder.files if name != file_name]
#     bot.answer_callback_query(call.id, text=f'Файл {file_name} удален!')
#     start(call.message)
#
# @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
# def delete_reminder(call):
#     chat_id = call.message.chat.id
#     reminder_index = int(call.data.split('_')[1])
#     users[chat_id].pop(reminder_index)
#     bot.answer_callback_query(call.id, text='Напоминание удалено!')
#     start(call.message)
#
# @bot.callback_query_handler(func=lambda call: call.data.startswith('done_'))
# def done_reminder(call):
#     chat_id = call.message.chat.id
#     reminder_index = int(call.data.split('_')[1])
#     reminder = users[chat_id][reminder_index]
#     reminder.done = True
#     bot.answer_callback_query(call.id, text='Напоминание выполнено!')
#     start(call.message)
#
# @bot.message_handler(func=lambda message: message.text == 'Выполненные дела')
# def done_reminders(message):
#     chat_id = message.chat.id
#     reminders = users.get(chat_id, [])
#     if not reminders:
#         bot.send_message(chat_id, 'У вас нет выполненных напоминаний.')
#         start(message)
#         return
#     for i, reminder in enumerate(reminders):
#         if reminder.done:
#             text = f'{i+1}. {reminder.text} ({reminder.date.strftime("%Y-%m-%d %H:%M")})'
#             bot.send_message(chat_id, text)
#             markup = types.InlineKeyboardMarkup()
#             btn1 = types.InlineKeyboardButton('Вернуть в текущие', callback_data=f'undone_{i}')
#             markup.add(btn1)
#             bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)
#     start(message)
#
# @bot.callback_query_handler(func=lambda call: call.data.startswith('undone_'))
# def undone_reminder(call):
#     chat_id = call.message.chat.id
#     reminder_index = int(call.data.split('_')[1])
#     reminder = users[chat_id][reminder_index]
#     reminder.done = False
#     bot.answer_callback_query(call.id, text='Напоминание возвращено в текущие!')
#     start(call.message)
#
# if __name__ == '__main__':
#     bot.polling()
#
#
#
