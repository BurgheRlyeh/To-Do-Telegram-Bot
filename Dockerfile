# Используем официальный образ Python 3
FROM python:3.8

# Создаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы с нашего локального компьютера в Docker контейнер
COPY . .

# Запускаем скрипт
CMD ["python", "./bot.py"]