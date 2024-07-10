import logging
import os
import requests
import time
from http import HTTPStatus
from sys import stdout

from telebot import TeleBot
from telebot.apihelper import ApiException
from dotenv import load_dotenv

from exceptions import HomeworksNameNotFound, StatusError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

last_status = {}


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(stream=stdout)
_handler.setLevel(logging.DEBUG)
_format = logging.Formatter('%(asctime)s - %(name)s - '
                            '[%(levelname)s] -> %(message)s')
_handler.setFormatter(_format)
log.addHandler(_handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            log.critical(f'Отсутствует переменная окружения: {token}')
            return False
    return True


def send_message(bot, message):
    """Посылаем сообщение в Telegramm."""
    try:
        log.debug('Посылаем сообщеие пользователю: \n' + message)
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except ApiException as err:
        log.error(f'Ошибка отправки сообщения: {err}', exc_info=True)
    else:
        log.debug('Сообщение пользователю отправлено.')


def get_api_answer(timestamp=0):
    """Запрашиваем API Yandex Practicum."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            message = f'Ошибка {response.status_code}: {response.reason}'
            log.error(message)
            raise Exception(message)
        return response.json()
    except requests.exceptions.RequestException as err:
        message = f'Ошибка при запросе к API: {err}'
        log.error(message)
        raise Exception(message)


def check_response(response):
    """Проверяем список ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')

    expected_keys = ['homeworks', 'current_date']
    for key in expected_keys:
        if key not in response:
            raise KeyError(f'В ответе API отсутствует ожидаемый ключ: {key}')

    if not isinstance(response["homeworks"], list):
        raise TypeError(
            'Неверный формат данных в ответе API: '
            'ключ "homeworks" не является списком'
        )
    return response['homeworks']


def parse_status(homework):
    """Проверяем на изменение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise HomeworksNameNotFound('Отсутствует ключ "homework_name".')
    status = homework.get('status')
    if not status or status not in HOMEWORK_VERDICTS:
        raise StatusError('Получен неизвестный статус.')
    if last_status.get(homework_name) == status:
        return None
    verdict = HOMEWORK_VERDICTS[status]
    last_status[homework_name] = status
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                homework_status = parse_status(homework)
                if homework_status:
                    message = homework_status
                    log.debug(message)
                    send_message(bot, message)
                else:
                    log.debug('Статус домашнего задания не изменился.')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            log.error(message)
            send_message(bot, message)
        log.debug('Ожидаем следующей проверки.')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
