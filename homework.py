import logging
import os
import time
import requests
import telegram

from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from requests.exceptions import RequestException
from telegram import Bot
from telegram.ext import Updater

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
RETRY_TIME = 60 * 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}

updater = Updater(token=TELEGRAM_TOKEN)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'main.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение пользователю в Telegram"""
    try:
        bot.send_message(CHAT_ID, message)
        logging.info(f'Бот отправил сообщение: {message}')
    except telegram.TelegramError as e:
        logging.error(
            f'Боту не удалось отправить сообщение. Ошибка: {e}'
        )
        raise


def get_api_answer(url, current_timestamp):
    """Получает ответ от API Практикума"""
    headers = {'Authorization': PRACTICUM_TOKEN}
    payload = {'from_date': current_timestamp}
    response = requests.get(
        url,
        headers=headers,
        params=payload
    )
    if response.status_code != 200:
        message = (
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
        logger.error(message)
        raise RequestException
    return response.json()


def parse_status(homework):
    """Получает последнюю работу и формирует сообщение пользователю"""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    verdict = HOMEWORK_STATUSES[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Анализирует ответ API и возвращает последнюю домашнюю работу """
    homeworks = response.get('homeworks')
    if not homeworks:
        message = 'Нет списка homeworks'
        logger.error(message)
        raise Exception(message)
    if len(homeworks) == 0:
        message = 'Список homeworks пуст'
        logger.error(message)
        raise Exception(message)
    status = homeworks[0]['status']
    if status not in HOMEWORK_STATUSES:
        message = f'Неожиданный статус: {status}'
        logger.error(message)
        raise Exception(message)
    return homeworks[0]


def main():
    """Запускает работу бота"""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            current_timestamp -= RETRY_TIME
            answer = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(answer)
            verdict = parse_status(homework)
            send_message(bot, verdict)
            time.sleep(RETRY_TIME)
        except NameError:
            message = "Отсутствует одна из обязательных переменных окружения"
            send_message(bot, message)
            logger.critical(message)
            continue
        except ValueError:
            message = "Отсутствует ожидаемый ключ в ответе API"
            send_message(bot, message)
            logger.error(message)
            continue
        except IndexError:
            logger.info('Список homeworks пуст')
            continue
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
            continue


if __name__ == '__main__':
    main()
