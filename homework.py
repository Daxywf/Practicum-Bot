import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

load_dotenv()


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 60 * 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
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
    'Ошибка сервера.'
    '{key} : {value}'
    'Эндпоинт: {url} '
    'Код ответа API: {code} '
    'Параметры запроса: {headers}, {params}'

)
NEW_STATUS = 'Изменился статус проверки работы "{homework_name}". {verdict}'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'
SEND_ERROR = 'Боту не удалось отправить сообщение. Ошибка: {error}'
MESSAGE_SENT = 'Бот отправил сообщение: {message}'
UNEXPECTED_STATUS = 'Неожиданный статус: {status}'
NO_KEY = 'Отсутствует ключ: {key}'
RESPONSE_NOT_DICT = 'Ответ не является словарём'
MISSING_VAR = 'Отсутствует одна из обязательных переменных окружения.'

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


class AnswerIsNot200Error(Exception):
    """Код ответа API не равен 200."""


class ServerError(Exception):
    """Сервер отправил сообщение об ошибке."""


def send_message(bot, message):
    """Отправляет сообщение пользователю в Telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info(MESSAGE_SENT.format(message=message))


def get_api_answer(current_timestamp):
    """Получает ответ от API Практикума."""
    request_parameters = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': current_timestamp}
    )
    try:
        response = requests.get(**request_parameters)
    except RequestException as error:
        raise ConnectionError(
            REQUEST_ERROR.format(
                error=error,
                **request_parameters,
            )
        )
    answer = response.json()
    if isinstance(answer, dict):  # Без этой строки код падают тесты от 08.11
        for key in ['code', 'error']:
            if key in answer:
                raise ServerError(
                    SERVER_ERROR.format(
                        **request_parameters,
                        key=key,
                        value=answer[key]
                    )
                )
    if response.status_code != 200:
        raise AnswerIsNot200Error(
            CODE_IS_NOT_200.format(
                code=response.status_code,
                **request_parameters
            )
        )
    return answer


def check_response(response):
    """Анализирует ответ API и возвращает последнюю домашнюю работу."""
    homeworks = response['homeworks']
    homework = homeworks[0]
    return homework


def parse_status(homework):
    """Получает последнюю работу и формирует сообщение пользователю."""
    for key in ['status', 'homework_name']:
        if key not in homework:  # parse_status_no status_key падает
            raise KeyError(NO_KEY.format(key=key))
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(UNEXPECTED_STATUS.format(status=status))
    return NEW_STATUS.format(
        homework_name=homework['homework_name'],
        verdict=VERDICTS[status]
    )


def check_tokens():
    """Проверяет наличие основных токенов."""
    for name in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'):
        if globals()[name] is None:
            message = MISSING_ENV_VARS.format(variable=name)
            logger.critical(message)
            return False
        return True  # test_check_tokens_false падает при выбрасывании ошибок


def main():
    """Основная логика работы бота."""
    if not check_tokens() is True:
        raise NameError(MISSING_VAR)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            answer = get_api_answer(ENDPOINT, timestamp)
            homework = check_response(answer)
            verdict = parse_status(homework)
            send_message(bot, verdict)
            timestamp = answer.get('current_date', timestamp)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logger.error(message)
            try:
                send_message(bot, message)
            except Exception as error:
                logger.error(SEND_ERROR.format(error=error))
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
