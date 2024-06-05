import pm
from usr.bin.components.abstract_service import AbstractService
from usr.utils.service_utils import Singleton
from usr.bin.components.monitor import ServiceMonitor

ENABLE_ = "enable"
NET_ = "NET"
DATACALL_ = "DATACALL"


class PMServiceMonitor(ServiceMonitor):

    @staticmethod
    def create_monitor(config=None):
        ps_service = PMService()
        psm = PMServiceMonitor(ps_service)
        if config is not None:
            psm.set_exception_handlers(config.get('exceptionHandlers', None))
        return psm


PM = "pm"


@Singleton
class PMService(AbstractService):
    def __init__(self, flag=1):
        super().__init__(PM)
        self.pm = pm
        self.__pm_lock = pm.create_wakelock("pm_lock", len("pm_lock"))
        self.__flag = flag
        self.__count = 0

    def lock(self):
        self.__count += 1
        self.pm.wakelock_lock(self.__pm_lock)

    def unlock(self):
        self.__count -= 1
        if self.count() < 1:
            self.pm.wakelock_unlock(self.__pm_lock)

    def count(self):
        if self.__count < 0:
            self.__count = 0
        return self.__count

    def auto_sleep(self, flag):
        self.pm.autosleep(flag)

    def register_event(self):
        self.pm.autosleep(1)
