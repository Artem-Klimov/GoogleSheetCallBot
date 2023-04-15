import logging
import os
from datetime import datetime

import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from telegram import ReplyKeyboardMarkup
from telegram.ext import (CommandHandler, ConversationHandler, Filters,
                          MessageHandler, Updater)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Установка настроек логирования
logging.basicConfig(
    level=logging.INFO,
)

# Инициализация Google Sheets API
CREDENTIALS_FILE = 'creds.json'
# ID Google Sheets документа (можно взять из его URL)
spreadsheet_id = '1gN45DAlVIO0AoQLzWJ4ztnNOmCFNglZ-H2_ZpcygeDE'
# Авторизуемся и получаем service — экземпляр доступа к API
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    CREDENTIALS_FILE,
    ['https://www.googleapis.com/auth/spreadsheets',
     'https://www.googleapis.com/auth/drive'])

client = gspread.authorize(credentials)
sheet = client.open('Таблица звонков').sheet1
# all_values = sheet.get_all_values()
buttons = ReplyKeyboardMarkup([['/Start', '/Cancel']])
# Определение состояний
USER_ID, CALLS, DROPS = range(3)


# Обработчик команды /start
def start(update, context):
    try:
        chat = update.effective_chat
        name = update.message.chat.first_name
        context.bot.send_message(
            chat_id=chat.id,
            text=f'Привет {name}!\n'
                 'Этот бот сохраняет введенные данные в Google Sheets.\n'
                 'Введите ID пользователя.',
            reply_markup=buttons
        )
        return USER_ID
    except Exception as e:
        logging.error(f'Ошибка в обработчике команды /start: {e}')
        raise


# Обработчик ввода ID пользователя
def process_user_id(update, context):
    user_id = update.message.text
    # Сохранение ID пользователя для дальнейшей обработки
    context.user_data['user_id'] = user_id
    logging.info(f"user_id = {user_id}")
    logging.info(f"user_id_user_data = {context.user_data.get('user_id')}")
    update.message.reply_text('Введите количество совершенных звонков:')
    return CALLS


# Обработчик ввода количества совершенных звонков
def process_calls(update, context):
    calls = update.message.text
    # Сохранение количества совершенных звонков
    context.user_data['calls'] = calls
    logging.info(f"calls = {calls}")
    logging.info(f"calls_user_data = {context.user_data.get('calls')}")
    update.message.reply_text('Введите количество сброшенных вызовов:')
    return DROPS


def process_drops(update, context):
    drops = update.message.text
    user_id = context.user_data.get('user_id')
    calls = context.user_data.get('calls')
    logging.info(f"drops = {drops}")
    print("drops-", drops,
          "user_id-", user_id,
          "calls-", calls)
    write_to_google_sheets(update, user_id, calls, drops)
    return ConversationHandler.END


def write_to_google_sheets(update, user_id, calls, drops):
    # Поиск строки с соответствующим ID пользователя
    now = datetime.now().strftime('%d/%m/%Y')
    cell = sheet.find(str(user_id))
    row = cell.row

    # Запись данных в соответствующие столбцы
    sheet.update_cell(row, 3, str(now))  # Текущая дата
    sheet.update_cell(row, 4, str(calls))  # Количество звонков
    sheet.update_cell(row, 5, str(drops))  # Количество сбросов
    update.message.reply_text('Спасибо! Данные сохранены:\n'
                              f'ID пользователя: {user_id}\n'
                              f'Количество звонков: {calls}\n'
                              f'Количество сбросов: {drops}')


def cancel(update, context):
    # Сброс состояний
    context.user_data.clear()
    update.message.reply_text('Действие отменено.')
    return ConversationHandler.END


def run_bot():
    # Создание экземпляра Updater и добавление обработчиков
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            USER_ID: [MessageHandler(Filters.text, process_user_id)],
            CALLS: [MessageHandler(Filters.text, process_calls)],
            DROPS: [MessageHandler(Filters.text, process_drops)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    updater.dispatcher.add_handler(conv_handler)

    # Запуск бота
    updater.start_polling()
    logging.info('Бот запущен.')
    updater.idle()


if __name__ == '__main__':
    run_bot()
