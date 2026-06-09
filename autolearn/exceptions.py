"""自定义异常体系"""


class AutoLearnError(Exception):
    pass


class LoginFailed(AutoLearnError):
    pass


class CourseNotFound(AutoLearnError):
    pass


class CaptchaError(AutoLearnError):
    pass


class RequestError(AutoLearnError):
    def __init__(self, message: str, url: str = "", status_code: int = 0):
        self.url = url
        self.status_code = status_code
        super().__init__(message)


class Non200Error(RequestError):
    pass


class RetryExhaustedError(RequestError):
    pass
