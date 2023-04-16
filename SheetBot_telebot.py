import logging
import os
from datetime import datetime

import telebot
from telebot import types
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

# Инициализация бота

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

CREDENTIALS_FILE = 'creds.json'

credentials = ServiceAccountCredentials.from_json_keyfile_name(
    CREDENTIALS_FILE,
    ['https://www.googleapis.com/auth/spreadsheets',
     'https://www.googleapis.com/auth/drive'])

client = gspread.authorize(credentials)
sheet = client.open('Таблица звонков').sheet1

# Установка настроек логирования
logging.basicConfig(
    level=logging.INFO,
)

markup = types.ReplyKeyboardMarkup()
btn2 = types.KeyboardButton('/cancel')
btn1 = types.KeyboardButton('/start')
markup.row(btn1, btn2)
btn3 = types.KeyboardButton('/get_id')
markup.row(btn3)
logging.debug('handle_message')

user_data = {"user_id": None,
             "calls": None,
             "drop_calls": None}


@bot.message_handler(commands=['cancel'])
def cancel(message):
    try:
        if 'user_id' in user_data:
            user_data['user_id'] = None
        if 'calls' in user_data:
            user_data['calls'] = None
        if 'drop_calls' in user_data:
            user_data['drop_calls'] = None
        bot.send_message(message.chat.id, 'Действие отменено, данные очищены.')
    except Exception as e:
        logging.error(f'Ошибка в обработчике команды /cancel: {e}')
        raise


# Функция обработки сообщения от пользователя
@bot.message_handler(commands=['get_id'])
def handle_name(message):
    logging.debug('find_id')
    bot.send_message(message.chat.id,
                     'Пожалуйста, введите Ваше имя и фамилию '
                     'или полное ФИО, включая букву "ё", '
                     'если она присутствует.\n'
                     'Убедитесь, что вводите без ошибок.')
    bot.register_next_step_handler(message, get_id)


def get_id(message):
    logging.debug('handle_name')
    logging.info('Поиск ID, вычисление координатов')
    try:
        partial_name = message.text
        all_values = sheet.get_all_values()
        name_col = None
        name_row = None
        for i, row in enumerate(all_values):
            for j, cell in enumerate(row):
                if partial_name in cell:
                    logging.info('Координаты найдены')
                    # Найдена ячейка с частичным совпадением
                    name_col = j
                    name_row = i+1
                    break
            if name_col and name_row:
                break
        if name_col and name_row:
            logging.info('Поиск ID по координатам')
            name_id = sheet.cell(name_row, name_col).value
            user_data['user_id'] = name_id
            logging.info(f'ID получен:{name_id}')
            bot.send_message(message.chat.id, f'Ваш ID: {name_id}')
        else:
            logging.info('ID не найден')
            bot.send_message(message.chat.id,
                             'Извините, ID не найден в системе.\n'
                             'Пожалуйста, проверьте правильность '
                             'введенных данных и попробуйте снова.')
    except Exception as e:
        logging.error(f'Ошибка в обработчике команды /Get_id: {e}')
        raise


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
                     f'Привет {message.from_user.first_name}!\n'
                     'Этот бот сохраняет введенные данные в Google Sheets.\n'
                     'Введите ID пользователя.\n'
                     'Что-бы узнать id напишите /Get_id',
                     reply_markup=markup)
    bot.register_next_step_handler(message, get_num_calls)


# Функция обработки введенного количества звонков
def get_num_calls(message):
    logging.debug('get_num_calls')
    user_id = message.text
    while not user_id.isdigit():
        logging.error('Введено нечисловое '
                      f'значение ID пользователя: {type(user_id)}')
        bot.reply_to(message, 'Пожалуйста, введите число.')
        # Рекурсивный вызов функции до ввода корректного числового значения
        bot.register_next_step_handler(message, get_num_calls)
        return

    logging.info(f'user_id = {user_id}')
    user_data['user_id'] = user_id

    bot.send_message(message.chat.id,
                     'Введите количество совершенных вызовов.')
    # Сохранение количества звонков в переменную для последующего использования
    bot.register_next_step_handler(message, get_num_dropped_calls)


# Функция обработки введенного количества сброшенных вызовов
def get_num_dropped_calls(message):
    logging.debug('get_num_dropped_calls')
    num_calls = message.text
    if message.text.isdigit():
        logging.info(f'num_dropped_calls = {num_calls}')
        user_data['calls'] = num_calls
        bot.reply_to(message, 'Введите количество вызовов:')
        bot.register_next_step_handler(message, write_to_google_sheets)
    else:
        logging.error('Введено нечисловое значение '
                      f'сброшенных вызовов: {type(num_calls)}')
        bot.reply_to(message, 'Пожалуйста, введите число.')
        # Рекурсивный вызов функции до ввода корректного числового значения
        bot.register_next_step_handler(message, get_num_dropped_calls)


def write_to_google_sheets(message):
    now = datetime.now().strftime('%d/%m/%Y')
    num_dropped_calls = message.text
    if message.text.isdigit():
        logging.info(f'num_dropped_calls = {num_dropped_calls}')
        user_data['drop_calls'] = num_dropped_calls

    else:
        logging.error('Введено нечисловое значение '
                      f'сброшенных вызовов: {type(num_dropped_calls)}')
        bot.reply_to(message, 'Пожалуйста, введите число.')
        # Рекурсивный вызов функции до ввода корректного числового значения
        bot.register_next_step_handler(message, write_to_google_sheets)

    user_id = user_data['user_id']
    num_calls = user_data['calls']

    if user_id and num_calls:
        logging.info(f'ID пользователя: {user_id}, '
                     f'Количество звонков: {num_calls}, '
                     f'Количество сброшенных вызовов: {num_dropped_calls}')

        # Поиск строки с соответствующим ID пользователя
        cell = sheet.find(str(user_id))
        row = cell.row

        # Запись данных в соответствующие столбцы
        sheet.update_cell(row, 4, str(now))  # Текущая дата
        sheet.update_cell(row, 5, str(num_calls))  # Количество звонков
        sheet.update_cell(row, 6, str(num_dropped_calls))  # Количество сбросов
        bot.send_message(message.chat.id, 'Спасибо! Данные сохранены:\n'
                                          f'ID пользователя: {user_id}\n'
                                          f'Количество звонков: {num_calls}\n'
                                          f'Количество сбросов: {num_dropped_calls}')
    else:
        bot.reply_to(message, 'Ошибка: данные не найдены. '
                              'Пожалуйста, попробуйте еще раз.')


# Запуск бота
logging.info('Бот запущен')
bot.polling()
