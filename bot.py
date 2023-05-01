import telebot
from telebot import types
import datetime
import threading
import time

bot = telebot.TeleBot('')  # замените YOUR_TOKEN_HERE на токен вашего бота

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


@bot.message_handler(commands=['cancel'])
def cancel(message):
    start(message)  # выводим клавиатуру с выбором действий при отмене


@bot.message_handler(func=lambda message: message.text == 'Создать напоминание')
def create_reminder(message):
    chat_id = message.chat.id
    users[chat_id] += [Reminder()]  # добавляем его в список напоминаний пользователя
    msg = bot.send_message(chat_id, 'Введите текст напоминания:')
    bot.register_next_step_handler(msg, process_text_step)  # переходим к следующему шагу


def process_text_step(message, reminder_index=-1):
    chat_id = message.chat.id
    users[chat_id][reminder_index].text = message.text

    if reminder_index != -1:
        bot.send_message(chat_id, 'Текст изменен!')
        start(message)  # выводим клавиатуру с выбором действий
        return

    bot.send_message(chat_id, 'Введите дату и время напоминания\nФормат: ГГГГ-ММ-ДД ЧЧ:ММ\nПример:')
    next_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
    msg = bot.send_message(chat_id, next_date)
    bot.register_next_step_handler(msg, process_date_step)


def process_date_step(message, reminder_index=-1):
    chat_id = message.chat.id
    try:
        date_str = message.text  # получаем дату от пользователя
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')  # преобразуем строку в объект datetime
        users[chat_id][reminder_index].date = date  # сохраняем дату в напоминании

        if reminder_index != -1:
            bot.send_message(chat_id, 'Дата изменена!')
            start(message)  # выводим клавиатуру с выбором действий
            return

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
        msg = bot.send_message(chat_id, 'Прикрепите файлы или нажмите /cancel для отмены:')
        bot.register_next_step_handler(msg, process_add_files_step, -1)
    else:
        bot.send_message(chat_id, 'Напоминание создано!')
        start(message)


def process_add_files_step(message, reminder_index=-1):
    chat_id = message.chat.id

    if message.content_type == 'document':
        file_id = message.document.file_id
        file_name = message.document.file_name

        reminder = users[chat_id][reminder_index]
        reminder.files += [(file_name, file_id)]

        bot.send_message(chat_id, f'Файл {file_name} добавлен!')
        msg = bot.send_message(chat_id, 'Прикрепите еще файлы или нажмите /cancel для отмены:')
        bot.register_next_step_handler(msg, process_add_files_step, reminder_index)

    elif message.content_type != 'text':
        msg = bot.send_message(chat_id, 'К сожалению, данный формат файлов пока не поддерживается\n'
                                        'Попробуйте отправить документ через раздел \"Файлы\" '
                                        'или нажмите /cancel для отмены')
        bot.register_next_step_handler(msg, process_add_files_step)

    elif reminder_index == -1:
        bot.send_message(chat_id, 'Напоминание создано!')
        start(message)

    else:
        start(message)


def reminder_created(message):
    chat_id = message.chat.id
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
        if reminder.done:
            continue

        markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
        markup.add(
            types.InlineKeyboardButton('Редактировать', callback_data=f'edit_{i}'),
            types.InlineKeyboardButton('Удалить', callback_data=f'delete_{i}'),
            types.InlineKeyboardButton('Выполнено', callback_data=f'done_{i}')
        )

        text = f'{i + 1}. {reminder.text} ({reminder.date.strftime("%Y-%m-%d %H:%M")})'
        bot.send_message(chat_id, text, reply_markup=markup)

        if reminder.files:
            bot.send_message(chat_id, 'Файлы:')
            for file_name, file_id in reminder.files:
                bot.send_document(chat_id, file_id, caption=file_name)
        # bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)

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
        bot.register_next_step_handler(msg, process_text_step, reminder_index)  # переходим к следующему шагу
    elif message.text == 'Изменить дату':
        bot.send_message(chat_id, 'Введите новую дату и время напоминания\nФормат: ГГГГ-ММ-ДД ЧЧ:ММ\nПример:')
        next_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
        msg = bot.send_message(chat_id, next_date)
        bot.register_next_step_handler(msg, process_date_step, reminder_index)  # переходим к следующему шагу
    elif message.text == 'Изменить файлы':
        if reminder.files:
            for file_name, file_id in reminder.files:
                markup = types.InlineKeyboardMarkup()  # создаем клавиатуру с выбором действий
                markup.add(
                    types.InlineKeyboardButton('Удалить', callback_data=f'delete_file_{reminder_index}_{file_name}')
                )
                bot.send_document(chat_id, file_id, caption=file_name, reply_markup=markup)
        msg = bot.send_message(chat_id, 'Прикрепите новые файлы или нажмите /cancel для отмены:')
        bot.register_next_step_handler(msg, process_files_step, reminder_index)  # переходим к следующему шагу


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_file_'))
def delete_file(call):
    data = call.data.split('_')
    reminder = users[call.message.chat.id][int(data[2])]
    reminder.files = [(name, file_id) for name, file_id in reminder.files if name != data[3]]
    bot.answer_callback_query(call.id, text=f'Файл {data[3]} удален!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_reminder(call):
    users[call.message.chat.id].pop(int(call.data.split('_')[1]))
    bot.answer_callback_query(call.id, text='Напоминание удалено!')
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('done_'))
def done_reminder(call):
    reminder = users[call.message.chat.id][int(call.data.split('_')[1])]
    reminder.done = True
    bot.answer_callback_query(call.id, text='Напоминание выполнено!')
    start(call.message)


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
            markup.add(types.InlineKeyboardButton('Вернуть в текущие', callback_data=f'undone_{i}'))
            bot.send_message(chat_id, 'Выберите действие:', reply_markup=markup)

    start(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith('undone_'))
def undone_reminder(call):
    reminder = users[call.message.chat.id][int(call.data.split('_')[1])]
    reminder.done = False
    bot.answer_callback_query(call.id, text='Напоминание возвращено в текущие!')
    start(call.message)


def check_reminders():
    while True:
        current_time = datetime.datetime.now()
        for chat_id, reminders in users.items():
            for reminder in reminders:
                if not reminder.done and reminder.date is not None and reminder.date <= current_time:
                    bot.send_message(chat_id, f'Напоминание: {reminder.text}')
                    if reminder.files:
                        bot.send_message(chat_id, 'Файлы:')
                        for file_name, file_id in reminder.files:
                            bot.send_document(chat_id, file_id, caption=file_name)

                    reminder.done = True
        time.sleep(10)  # проверяем напоминания каждую минуту


if __name__ == '__main__':
    threading.Thread(target=check_reminders).start()
    bot.polling()  # запускаем бота
