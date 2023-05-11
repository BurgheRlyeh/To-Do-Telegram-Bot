# Используем официальный образ Python 3
FROM python:3.8-slim-buster

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы с нашего локального компьютера в Docker контейнер
COPY bot.py /app
COPY config.py /app

# Устанавливаем необходимые библиотеки
RUN pip install telebot

# Запускаем скрипт
CMD ["python", "bot.py"]