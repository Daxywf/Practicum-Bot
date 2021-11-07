import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 60 * 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
HEADERS = {'Authorization': PRACTICUM_TOKEN}
MISSING_ENV_VARS = "Отсутствует одна из обязательных переменных окружения"
REQUEST_ERROR = (
    'Ошибка запроса.''Эндпоинт: {endpoint} '
    'Код ответа API: {code}'
    'Параметры запроса: {headers}, {params}'
)
SERVER_ERROR = 'Ошибка сервера: {error}'
NEW_STATUS = 'Изменился статус проверки работы "{homework_name}". {verdict}'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'
SEND_ERROR = 'Боту не удалось отправить сообщение. Ошибка: {e}'
MESSAGE_SENT = 'Бот отправил сообщение: {message}'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    f'{__file__}.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение пользователю в Telegram."""
    try:
        bot.send_message(CHAT_ID, message)
        logger.info(MESSAGE_SENT.format(message=message))
    except telegram.TelegramError as e:
        raise e(SEND_ERROR.format(error=e))


def get_api_answer(url, current_timestamp):
    """Получает ответ от API Практикума."""
    payload = {'from_date': current_timestamp}
    response = requests.get(
        url,
        headers=HEADERS,
        params=payload
    )
    answer = response.json()
    if response.status_code != 200:
        error = answer.get('error')
        if error:
            message = SERVER_ERROR.format(error=error['error'])
            logger.error(message)
            print(message)
        raise Exception(
            REQUEST_ERROR.format(
                endpoint=ENDPOINT,
                code=response.status_code,
                headers=HEADERS,
                params=payload
            )
        )
    return answer


def parse_status(homework):
    """Получает последнюю работу и формирует сообщение пользователю."""
    verdict = HOMEWORK_VERDICTS[homework['status']]
    homework_name = homework['homework_name']
    return NEW_STATUS.format(homework_name=homework_name, verdict=verdict)


def check_response(response):
    """Анализирует ответ API и возвращает последнюю домашнюю работу."""
    homeworks = response['homeworks']
    homework = homeworks[0]
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        message = f'Неожиданный статус: {status}'
        print(message)
        raise NameError(message)
    return homework


def main():
    """Запускает работу бота."""
    if TELEGRAM_TOKEN is None or PRACTICUM_TOKEN is None or CHAT_ID is None:
        message = MISSING_ENV_VARS
        logger.critical(message)
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            answer = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(answer)
            verdict = parse_status(homework)
            send_message(bot, verdict)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logger.error(message)
            send_message(bot, message)
            print(message)


if __name__ == '__main__':
    main()
