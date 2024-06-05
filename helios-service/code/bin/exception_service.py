from usr.bin.components.abstract_service import AbstractService
from usr.bin.components.monitor import ServiceMonitor
from usr.utils.service_utils import Singleton


class ExceptionServiceMonitor(ServiceMonitor):
    @staticmethod
    def create_monitor(config=None):
        esm = ExceptionServiceMonitor(ExceptionService())
        if config is not None:
            esm.set_exception_handlers(config.get('exceptionHandlers', None))
        return esm


@Singleton
class ExceptionService(AbstractService):

    def __init__(self):
        super().__init__("EXCEPTION")
        self.error_message = []

    def handler_error(self, *args, **kwargs):
        msg = "message"
        em = kwargs.get(msg, False)
        if em:
            print(em[msg])

    def prepare_before_start(self):
        self.signal.connect(self.handler_error, sender="anonymous")

    def __call__(self, message):
        self.send_msg(message=message)
