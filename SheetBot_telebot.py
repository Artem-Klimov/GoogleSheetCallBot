import logging
import os
from datetime import datetime

import gspread
import telebot
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from telebot import types

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

logging.debug('handle_message')

user_data = {"user_id": None,
             "calls": None,
             "drop_calls": None}


@bot.message_handler(commands=['cancel'])
def cancel(message, cancel_send_info=True):
    try:
        if 'user_id' in user_data:
            user_data['user_id'] = None
        if 'calls' in user_data:
            user_data['calls'] = None
        if 'drop_calls' in user_data:
            user_data['drop_calls'] = None
        logging.info(f'Данные очищенные. user_data= {user_data}')

        if cancel_send_info is True:
            bot.send_message(message.chat.id,
                             'Действие отменено, данные очищены.')
            start(message)

        if cancel_send_info is False:
            return

        cancel_send_info = True

    except Exception as e:
        logging.error(f'Ошибка в обработчике команды /cancel: {e}')
        raise


@bot.message_handler(commands=['start'])
def start(message):
    '''StartStatus:
    1 - Приветствие, описание, ввод, подсказка
    2 - Ввод, подсказка
    '''
    # флаг, который устанавливается при нажатии кнопки "получить id"
    global get_id_pressed
    get_id_pressed = False
    StartStatus = 1
    MarkupControl = types.ReplyKeyboardMarkup(resize_keyboard=True)
    MarkupControl1 = types.KeyboardButton('/start')
    MarkupControl2 = types.KeyboardButton('/cancel')
    MarkupControl.add(MarkupControl1, MarkupControl2)
    MarkupControl3 = types.KeyboardButton('/get_id')
    MarkupControl.add(MarkupControl3)

    MarkupGetId = types.InlineKeyboardMarkup()
    MarkupGetId1 = types.InlineKeyboardButton('Получить id',
                                              callback_data='get_id')
    MarkupGetId.row(MarkupGetId1)

    if StartStatus == 1:
        bot.send_message(
            message.chat.id,
            f'Привет {message.from_user.first_name}!\n'
            'Этот бот сохраняет введенные данные в Google Sheets.\n'
            'Введите ID пользователя.\n'
            'Чтобы узнать id нажмите /get_id',
            reply_markup=MarkupGetId
        )

    if StartStatus == 2:
        bot.send_message(
            message.chat.id,
            'Введите ID пользователя.\n'
            'Что-бы узнать id нажмите /get_id')

    # проверяем, была ли нажата кнопка "получить id"
    if not get_id_pressed:
        bot.register_next_step_handler(message, get_num_calls)
    else:
        handle_name(message)  # вызываем функцию, которая запрашивает ФИО

        # сбрасываем флаг после обработки нажатия кнопки
        get_id_pressed = False


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
    global MarkupGetId
    logging.debug('handle_name')
    logging.info('Поиск ID, вычисление координат')
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
            if enumerate(name_id):
                logging.info(f'ID получен:{name_id}')
                bot.send_message(message.chat.id, f'Ваш ID: {name_id}')
            else:
                logging.error(f'ID - нечисловое значение: {name_id}')
                bot.send_message(message.chat.id,
                                 'Извините, произошла ошибка, '
                                 'сервер выдал нечисловое значение ID')
        else:
            logging.info('ID не найден')
            bot.send_message(message.chat.id,
                             'Извините, ID не найден в системе.\n'
                             'Пожалуйста, проверьте правильность '
                             'введенных данных и попробуйте снова.',
                             reply_markup=MarkupGetId)
    except Exception as e:
        logging.error(f'Ошибка в обработчике команды /Get_id: {e}')
        raise


@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(callback_query):
    global get_id_pressed
    user_id = user_data['user_id']
    num_calls = user_data['calls']
    num_dropped_calls = user_data['drop_calls']
    if callback_query.data == 'Отправить':
        write_to_google_sheets(num_dropped_calls, user_id, num_calls)
        bot.edit_message_text(chat_id=callback_query.message.chat.id,
                              message_id=callback_query.message.message_id,
                              text="Спасибо, данные сохранены.")
    elif callback_query.data == 'Начать сначала':
        cancel(callback_query.message)
        bot.delete_message(chat_id=callback_query.message.chat.id,
                           message_id=callback_query.message.message_id)
    elif callback_query.data == "get_id":
        cancel_send_info = False
        cancel(callback_query.message, cancel_send_info)
        get_id_pressed = True  # устанавливаем флаг, что кнопка была нажата
        handle_name(callback_query.message)


def get_num_calls(message):
    global get_id_pressed
    logging.debug('get_num_calls')
    user_id = message.text

    logging.info('get cancel')
    if message.text == '/cancel':
        logging.info('cancel')
        cancel(message)
        return
    if get_id_pressed is False:
        while not user_id.isdigit():
            logging.error('Введено нечисловое '
                          f'значение ID пользователя: {type(user_id)}')
            bot.reply_to(message, 'Пожалуйста, введите число.')
            # Рекурсивный вызов функции до ввода корректного числового значения
            bot.register_next_step_handler(message, get_num_calls)
            return
    else:
        return

    user_data['user_id'] = user_id
    get_id_pressed = False
    logging.info(f'user_id = {user_id}')

    bot.send_message(message.chat.id,
                     'Введите количество совершенных вызовов.')
    bot.register_next_step_handler(message, get_num_dropped_calls)


# Функция обработки введенного количества сброшенных вызовов
def get_num_dropped_calls(message):
    logging.debug('get_num_dropped_calls')
    num_calls = message.text

    if message.text == '/cancel':
        cancel_send_info = False
        cancel(message, cancel_send_info)
        return

    while not num_calls.isdigit():
        logging.error('Введено нечисловое '
                      f'значение ID пользователя: {type(num_calls)}')
        bot.reply_to(message, 'Пожалуйста, введите число.')
        bot.register_next_step_handler(message, get_num_dropped_calls)
        return

    user_data['calls'] = num_calls
    logging.info(f'num_dropped_calls = {num_calls}')
    bot.send_message(message.chat.id, 'Введите количество сброшенных вызовов:')
    bot.register_next_step_handler(message, save_dropped_calls)


def conf_apply(message, user_id, num_calls, num_dropped_calls):
    MarkupConf = types.InlineKeyboardMarkup()
    MarkupRight = types.InlineKeyboardButton('Отправить данные✅',
                                             callback_data='Отправить')
    MarkupErong = types.InlineKeyboardButton('Начать сначала❌',
                                             callback_data='Начать сначала')
    MarkupConf.row(MarkupRight, MarkupErong)

    # Запись данных в соответствующие столбцы
    bot.send_message(
        message.chat.id,
        'Вы внесли следующие данные:\n'
        f'ID пользователя: {user_id}\n'
        f'Количество звонков: {num_calls}\n'
        f'Количество сбросов: {num_dropped_calls}\n'
        'Если все верно, то выберите «Отправить данные»',
        reply_markup=MarkupConf)


def save_dropped_calls(message):
    num_dropped_calls = message.text

    if message.text == '/cancel':
        cancel(message)
        return

    while not num_dropped_calls.isdigit():
        logging.error('Введено нечисловое '
                      'значение ID пользователя: '
                      f'{type(num_dropped_calls)}')
        bot.reply_to(message, 'Пожалуйста, введите число.')
        bot.register_next_step_handler(message, save_dropped_calls)
        return

    user_data['drop_calls'] = num_dropped_calls
    user_id = user_data['user_id']
    num_calls = user_data['calls']
    logging.info(f'num_dropped_calls = {num_dropped_calls}')

    if user_id and num_calls and num_dropped_calls:
        conf_apply(message, user_id, num_calls, num_dropped_calls)
        logging.info(f'ID пользователя: {user_id}, '
                     f'Количество звонков: {num_calls}, '
                     f'Количество сброшенных вызовов: {num_dropped_calls}')

        logging.debug('Данные переданы в функцию для подтверждения')
    else:
        bot.reply_to(message, 'Ошибка: данные не найдены. '
                              'Пожалуйста, попробуйте еще раз.')


def write_to_google_sheets(num_dropped_calls, user_id, num_calls):
    logging.debug('write_to_google_sheets')
    date = datetime.now().strftime('%d/%m/%Y')
    # Поиск строки с соответствующим ID пользователя
    cell = sheet.find(str(user_id))
    row = cell.row

    sheet.update_cell(row, 4, str(date))  # Текущая дата
    sheet.update_cell(row, 5, str(num_calls))  # Количество звонков
    sheet.update_cell(row, 6, str(num_dropped_calls))  # Количество сбросов
    logging.info('Данные сохранены в Google Sheets')


# Запуск бота
logging.info('Бот запущен')
bot.polling()
