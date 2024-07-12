from json import JSONDecodeError
import logging
import os
import requests
import time
from http import HTTPStatus
from sys import stdout

from telebot import TeleBot
from telebot.apihelper import ApiException
from dotenv import load_dotenv

from exceptions import (HomeworksNameNotFound,
                        MessageSendError,
                        StatusError,
                        YandexApiError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
SECOND_IN_MONTH = 2592000
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(stream=stdout)
_handler.setLevel(logging.DEBUG)
_format = logging.Formatter('%(asctime)s -(%(name)s)- '
                            '[%(levelname)s] -> %(message)s')
_handler.setFormatter(_format)
log.addHandler(_handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    log.debug('Проверяем наличие необходимых переменных окружения.')
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    token_error = [token for token in tokens if token is None]
    if token_error:
        for token in token_error:
            log.critical(f'Отсутствует переменная окружения: {token} \n'
                         'Программа принудительно остановленна')
        return False
    log.debug('Переменные окружения найдены. Продолжаем загрузку....')
    return True


def send_message(bot, message):
    """Посылаем сообщение в Telegramm."""
    try:
        log.debug('Посылаем сообщеие пользователю: \n' + message)
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except ApiException as err:
        raise MessageSendError('Произошла ошибка при отправке '
                               f'сообщения в Telegram: {err}')
    else:
        log.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp=0):
    """Запрашиваем API Yandex Practicum."""
    log.debug('Посылаем запрос к API Yandex.')
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException as err:
        raise YandexApiError(f'Ошибка при запросе к API: {err}')
    else:
        if response.status_code != HTTPStatus.OK:
            raise YandexApiError(f'Ошибка {response.status_code}: '
                                 f'{response.reason}')
        log.debug('Ответ от API получен.')
        try:
            api_answer = response.json()
        except JSONDecodeError:
            raise JSONDecodeError('Ошибка декодирования Json.')
        return api_answer


def check_response(response):
    """Проверяем список ответ API на соответствие документации."""
    log.debug('Проверяем ответ API на соответствие критериям.')
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
    log.debug('Ответ соответствует заданным параметрам.')
    return response['homeworks']


def parse_status(homework):
    """Проверяем на изменение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise HomeworksNameNotFound('Отсутствует ключ "homework_name".')
    status = homework.get('status')
    if not status or status not in HOMEWORK_VERDICTS:
        raise StatusError('Получен неизвестный статус.')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    log.debug('Запускаем программу.')
    if not check_tokens():
        return

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - SECOND_IN_MONTH
    last_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            log.debug('Проверяем статус домашнего задания.')
            if homeworks:
                homework_status = parse_status(homeworks[0])
                log.debug(homework_status)
                send_message(bot, homework_status)
                timestamp = response.get('current_date', timestamp)
            else:
                log.debug('Статус домашнего задания не изменился.')
        except MessageSendError as error:
            log.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            log.error(message)
            if message != last_error:
                send_message(bot, message)
                last_error = message
        log.debug(f'Следующая проверка через {RETRY_PERIOD / 60} мин.')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
