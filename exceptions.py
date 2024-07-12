class TokenError(Exception):
    """Ошибка: отсутствие токена."""

    pass


class StatusError(Exception):
    """Ошибка: неверный статус."""

    pass


class HomeworksNotFound(Exception):
    """Ошибка: отсутствует ключ 'homework' в ответе."""

    pass


class HomeworksNameNotFound(Exception):
    """Ошибка: отсутствует ключ 'homework_name' в ответе."""

    pass


class MessageSendError(Exception):
    """Ошибка: сообщение не отправлено."""

    pass


class YandexApiError(Exception):
    """Ошибка запроса к Api Yandex."""

    pass
