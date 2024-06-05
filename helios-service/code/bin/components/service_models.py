__all__ = [
    "QMessageModel"
]


class ModelDTO(object):
    def model_to_dict(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self.model_to_dict(*args, **kwargs)


class QMessageModel(ModelDTO):
    def __init__(self, ms_id=None, msg_type=0xFF, message=None, sender=None, from_event=None, lock_msg=None):
        self.__msg_type = msg_type
        self.__message_id = ms_id
        self.__message = message
        self.__sender = "anonymous" if sender is None else sender
        self.__from_event = from_event
        self.__lock_msg = lock_msg

    @property
    def msg_type(self):
        return self.__msg_type

    @property
    def lock_msg(self):
        return self.__lock_msg

    @property
    def message_id(self):
        return self.__message_id

    @property
    def sender(self):
        return self.__sender

    @property
    def message(self):
        return self.__message

    @property
    def from_event(self):
        return self.__from_event

    def model_to_dict(self):
        return dict(message_id=self.message_id, msg_type=self.msg_type, message=self.message, sender=self.sender,
                    from_event=self.from_event)


class LockMsgModel(ModelDTO):
    """传输对象"""

    def __init__(self, lock):
        self.__lock = lock
        self.__msg = dict(message=None)

    @property
    def msg(self):
        return self.__msg

    @msg.setter
    def msg(self, msg):
        self.__msg = msg

    @property
    def lock(self):
        return self.__lock

    def model_to_dict(self, *args, **kwargs):
        return dict(lock=self.__lock, msg=self.__msg)
