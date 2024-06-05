__all__ = [
    "CloudService",
    "CloudServiceMonitor",
]

from usr.bin.components.abstract_service import AbstractService
from usr.bin.components.monitor import ServiceMonitor
from usr.utils.service_utils import Singleton
from usr.bin.components.OTA import UCloudOTA
import _thread

SH_UPGRADE = 1
BIN_UPGRADE = 0
ENABLE_ = "enable"


class CloudServiceMonitor(ServiceMonitor):
    @staticmethod
    def create_monitor(config=None):
        if config is None:
            return None
        level = 0
        try:
            level = config.get("level", 0)
            uid = config["params"]["uid"]
            module_type = config["params"]["module_type"]
            pk = config["params"]["pk"]
            battery = config["params"].get("battery", 100)
            reboot = config["params"].get("reboot", False)
            cloud_service = CloudService(uid=uid, module_type=module_type, pk=pk, battery=battery, reboot=bool(reboot))
        except Exception as e:
            return None
        else:
            m = CloudServiceMonitor(cloud_service)
            m.set_level(level)
        if config is not None:
            m.set_exception_handlers(config.get('exceptionHandlers', None))
        return m


@Singleton
class CloudService(AbstractService):
    def __init__(self, uid, module_type, pk, battery=100, reboot=False):
        super().__init__("CLOUD")
        self.reboot = reboot
        self.module_type = module_type
        self.pk = pk
        self.uid = uid
        self.ota_upgrade = UCloudOTA(battery)
        self.__upgrade_status_info = {
            SH_UPGRADE: None,
            BIN_UPGRADE: None
        }
        self.server_status = {
            SH_UPGRADE: {ENABLE_: True},
            BIN_UPGRADE: {ENABLE_: False}
        }

    @property
    def upgrade_status_info(self):
        return self.__upgrade_status_info

    def set_enable(self, sr, enable):
        """set start"""
        self.server_status[sr][ENABLE_] = enable

    def __upgrade_sh(self):
        # 触发升级脚本操作
        if self.server_status[SH_UPGRADE][ENABLE_]:
            code = self.ota_upgrade.start_upgrade_sh_event(self.module_type, self.uid, self.pk, reboot=self.reboot)
            self.send_msg(message=dict(code=code), msg_type=SH_UPGRADE)

    def __upgrade_bin(self):
        # 触发升级bin包操作
        if self.server_status[BIN_UPGRADE][ENABLE_]:
            code = self.ota_upgrade.start_upgrade_bin_event(self.module_type, self.uid, self.pk, reboot=self.reboot)
            self.send_msg(message=dict(code=code), msg_type=BIN_UPGRADE)

    def _status_update(self, *args, **kwargs):
        msg = "message"
        em = kwargs.get(msg, False)
        if em:
            msg_type = em["msg_type"]
            self.__upgrade_status_info[msg_type] = em[msg]["code"]

    def get_app_code(self):
        return self.__upgrade_status_info[SH_UPGRADE]

    def prepare_before_start(self):
        self.signal.connect(self._status_update, sender="anonymous")

    def start(self):
        super().start()
        # _thread.start_new_thread(self.__upgrade_bin, ())
        _thread.start_new_thread(self.__upgrade_sh, ())

    def commit_log(self, message):
        self.ota_upgrade.commit_log(self.pk, message)
