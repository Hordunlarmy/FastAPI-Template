class CustomError(Exception):
    """
    Custom exception class for errors with HTTP status codes.
    """

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.http_status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        return f"{self.http_status_code}: {self.message}"
