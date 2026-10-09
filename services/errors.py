"""Errors that services raise. app.py turns them into clean JSON responses."""


class AppError(Exception):
    status_code = 400

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    status_code = 400


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409
