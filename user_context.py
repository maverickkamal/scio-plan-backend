import threading

class UserContext:
    _local = threading.local()

    @classmethod
    def set_user_id(cls, user_id):
        cls._local.user_id = user_id

    @classmethod
    def get_user_id(cls):
        return getattr(cls._local, 'user_id', None)

    @classmethod
    def clear_user_id(cls):
        if hasattr(cls._local, 'user_id'):
            del cls._local.user_id