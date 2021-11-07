import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from requests.models import HTTPError
from telegram import Bot

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 60 * 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
HEADERS = {'Authorization': PRACTICUM_TOKEN}
MISSING_ENV_VARS = (
    "Отсутствует одна из обязательных переменных окружения: "
    "{variable}"
)
REQUEST_ERROR = (
    'Ошибка запроса.'
    'Эндпоинт: {endpoint} '
    'Код ответа API: {code} '
    'Параметры запроса: {headers}, {params}'
)
SERVER_ERROR = (
    'Ошибка сервера: {error}'
    'Эндпоинт: {endpoint} '
    'Код ответа API: {code} '
    'Параметры запроса: {headers}, {params}'
)
NEW_STATUS = 'Изменился статус проверки работы "{homework_name}". {verdict}'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'
SEND_ERROR = 'Боту не удалось отправить сообщение. Ошибка: {e}'
MESSAGE_SENT = 'Бот отправил сообщение: {message}'
BAD_STATUS = 'Неожиданный статус: {status}'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    f'{__file__}.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
console_out = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(console_out)


def send_message(bot, message):
    """Отправляет сообщение пользователю в Telegram."""
    bot.send_message(CHAT_ID, message)
    logger.info(MESSAGE_SENT.format(message=message))


def get_api_answer(url, current_timestamp):
    """Получает ответ от API Практикума."""
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=payload
        )
    except ConnectionError:
        raise ConnectionError(
            'Ошибка сети. Параметры запроса: '
            f'{url}, {HEADERS}, {payload}'
        )
    answer = response.json()
    if 'code' and 'error' in answer.keys():
        raise HTTPError(
            SERVER_ERROR.format(
                error=answer['error']['error'],
                endpoint=ENDPOINT,
                code=response.status_code,
                headers=HEADERS,
                params=payload
            )
        )
    if response.status_code != 200:
        raise HTTPError(
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
    return NEW_STATUS.format(
        homework_name=homework['homework_name'],
        verdict=VERDICTS[homework['status']]
    )


def check_response(response):
    """Анализирует ответ API и возвращает последнюю домашнюю работу."""
    homeworks = response['homeworks']
    homework = homeworks[0]
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(BAD_STATUS.format(status=status))
    return homework


def main():
    """Запускает работу бота."""
    for name in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'CHAT_ID'):
        if globals()[name] is None:
            logger.critical(MISSING_ENV_VARS.format(variable=name))
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    timestamp = current_timestamp - RETRY_TIME
    while True:
        try:
            answer = get_api_answer(ENDPOINT, timestamp)
            homework = check_response(answer)
            verdict = parse_status(homework)
            send_message(bot, verdict)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logger.error(message)
            send_message(bot, message)
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
