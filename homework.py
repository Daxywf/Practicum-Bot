import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException
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
    'Ошибка при выполнении запроса: {error}.'
    'Эндпоинт: {url} '
    'Параметры запроса: {headers}, {params}'
)
CODE_IS_NOT_200 = (
    'Код ответа отличается от 200'
    'Эндпоинт: {url} '
    'Код ответа API: {code} '
    'Параметры запроса: {headers}, {params}'
)
SERVER_ERROR = (
    'Ошибка сервера: {error}'
    'Код ошибки {server_code}'
    'Эндпоинт: {url} '
    'Код ответа API: {code} '
    'Параметры запроса: {headers}, {params}'
)
NEW_STATUS = 'Изменился статус проверки работы "{homework_name}". {verdict}'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'
SEND_ERROR = 'Боту не удалось отправить сообщение. Ошибка: {error}'
MESSAGE_SENT = 'Бот отправил сообщение: {message}'
UNEXPECTED_STATUS = 'Неожиданный статус: {status}'

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
    request_parameters = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params=payload
    )
    try:
        response = requests.get(**request_parameters)
    except RequestException as error:
        raise error(
            REQUEST_ERROR.format(
                error=error,
                **request_parameters,
            )
        )
    answer = response.json()
    for key in answer.keys():
        if key == 'code' or key == 'error':
            raise RequestException(
                SERVER_ERROR.format(
                    error=answer['error'],
                    sevrer_code=answer['code'],
                    code=response.status_code,
                    **request_parameters
                )
            )
    if response.status_code != 200:
        raise RequestException(
            CODE_IS_NOT_200.format(
                code=response.status_code,
                **request_parameters
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
        raise ValueError(UNEXPECTED_STATUS.format(status=status))
    return homework


def main():
    """Запускает работу бота."""
    for name in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'CHAT_ID'):
        if globals()[name] is None:
            logger.critical(MISSING_ENV_VARS.format(variable=name))
            raise NameError(MISSING_ENV_VARS.format(variable=name))
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            answer = get_api_answer(ENDPOINT, current_timestamp - RETRY_TIME)
            homework = check_response(answer)
            verdict = parse_status(homework)
            send_message(bot, verdict)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logger.error(message)
            try:
                send_message(bot, message)
            except telegram.TelegramError as error:
                logger.error(SEND_ERROR.format(error=error))
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
