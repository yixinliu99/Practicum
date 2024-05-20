class MaximumRetryLimitExceeded(Exception):
    def __init__(self, max_retries: int, message: str) -> None:
        self.message = (
            f"Maximum retry limit {max_retries} exceeded. Exception: {message}"
        )
        super().__init__(self.message)


def retry(times, exceptions):
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    print(
                        'Exception thrown when attempting to run %s, attempt '
                        '%d of %d' % (func, attempt, times)
                    )
                    attempt += 1
            return func(*args, **kwargs)

        return newfn

    return decorator


def get_data_types():
    try:
        from flask import current_app
        datatypes = current_app.datatypes
    except RuntimeError:
        from DataTypes import DataTypes
        vs = {}
        with open("../.env", 'r') as file:
            for line in file:
                key, value = line.strip().split(' = ')
                vs[key] = value
        datatypes = DataTypes(vs)

    return datatypes
