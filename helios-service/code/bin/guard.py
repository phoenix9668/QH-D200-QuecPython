from usr.utils.JsonParserUtils import JsonParser
from usr.bin.exception_service import ExceptionService
from usr.utils.service_utils import Singleton
from usr.bin.components.monitor import MonitorInterface
from usr.bin.log_service import LogAdapter
import uos as os

__GROUP_ID = "qpy.quectel.com"
__ARTIFACT_ID = "qpy-framework"
__VERSION = "1.0.0.RELEASE"


def version():
    return {"GROUP_ID": __GROUP_ID, "artifact_id": __ARTIFACT_ID, "VERSION": __VERSION}


@Singleton
class Guard(object):
    def __init__(self):
        self.monitor_service = set()
        self.timer = None
        self.__status = 0

    def register_monitor(self, monitor):
        self.monitor_service.add(monitor)

    def start(self):
        for monitor in self.monitor_service:
            monitor.start()
        self.__status = 1

    def reload_level(self):
        for monitor in self.monitor_service:
            monitor.set_level(0)
            monitor.start()
        self.__status = 1

    def stop(self):
        for monitor in self.monitor_service:
            monitor.stop()
        self.__status = 0

    def status(self):
        return self.__status

    def upgrade(self):
        pass

    def monitor_map(self):
        return {m.service.name: m.service for m in self.monitor_service}


@Singleton
class GuardContext(object):

    def __init__(self):
        self.__guard = Guard()
        self.system_config = {}
        self.service_config = {}
        self.config_map = {
            "/usr/etc/system_config": self.system_config,
            "/usr/etc/app_config": self.service_config
        }
        self.config_parser = JsonParser()
        self.monitor_map = dict()
        self.error_handler = ExceptionService()
        self.error_handler.start()

    def servers(self):
        return self.monitor_map.copy()

    def get_server(self, name):
        return self.monitor_map[name]()

    def stop_server(self, name):
        return self.monitor_map[name].stop()

    @staticmethod
    def get_logger(name):
        return LogAdapter(name)

    @staticmethod
    def path_exist(check_path):
        try:
            os.stat(check_path)
        except Exception as e:
            return 0
        else:
            return 1

    def load_config_definitions(self):
        # load config
        # root path /usr/etc
        root_path = "/usr/etc/"
        stat = self.path_exist(root_path)
        if not stat:
            return
        self.load_configs(root_path)

    def load_configs(self, root_path):

        # system_path of service /usr/etc/system_config
        stat = self.path_exist(root_path)
        if not stat:
            self.error_handler("[   WARN    ] {} path is not exist".format(root_path))
            return True
        for par_path in os.listdir(root_path):
            abs_path = root_path + par_path
            for sub_path in os.listdir(abs_path):
                truth_path = abs_path + "/" + sub_path
                rep_d = self.config_parser.parse(truth_path)
                if rep_d["status"] == 0:
                    # 错误日志收集
                    self.error_handler("[   WARN    ] read {} status {}".format(truth_path, 0))
                else:
                    self.config_map[abs_path][sub_path] = rep_d["data"]

    def create_monitors(self):
        # 创建monitors
        monitor_map = dict()
        monitor_map.update(self.create_system_monitors())
        monitor_map.update(self.create_app_monitors())
        self.monitor_map = monitor_map

    def start(self):
        # 启动守卫  拉起所有的服务
        self.__guard.start()

    def register_monitors(self):
        # 注册monitor
        for k, v in self.monitor_map.items():
            self.__guard.register_monitor(v)

    def register_monitor(self, k, v):
        flag = False
        if isinstance(v, MonitorInterface) and isinstance(k, str):
            self.monitor_map[k] = v
            self.__guard.register_monitor(v)
            flag = not flag
        return flag

    def refresh(self):
        self.load_config_definitions()
        # 初始化monitor
        self.create_monitors()
        self.register_monitors()
        self.start()

    def reload(self):
        # 刷新通知
        self.__guard.reload_level()

    def create_system_monitors(self):
        monitor_map = dict()
        try:
            from usr.bin.net_service import NetServiceMonitor
            NET = "net"
            net_monitor = NetServiceMonitor.create_monitor(self.system_config.get(NET, None))
            monitor_map[NET] = net_monitor
            print("[    OK     ] create sys monitor net service")
        except Exception as e:
            # 异常重定向
            self.error_handler("[   FAILED  ] load net monitor error reason:{}".format(e))

        try:
            from usr.bin.log_service import LogServiceMonitor
            LOG = "log"
            log_monitor = LogServiceMonitor.create_monitor(self.system_config.get(LOG, None))
            monitor_map[LOG] = log_monitor
            print("[    OK     ] create sys monitor log service")
        except Exception as e:
            self.error_handler("[   FAILED  ] load log monitor error reason:{}".format(e))
        return monitor_map

    def create_app_monitors(self):
        monitor_map = dict()
        try:
            from usr.bin.media_service import MediaServiceMonitor
            MEDIA = "media"
            md_monitor = MediaServiceMonitor.create_monitor(self.service_config.get(MEDIA, None))
            if md_monitor is not None:
                monitor_map[MEDIA] = md_monitor
            else:
                raise Exception("media service load error")
            print("[    OK     ] create app monitor media service")
        except Exception as e:
            # 异常重定向
            self.error_handler("[   FAILED  ] load exception monitor error reason: [{}]".format(e))

        try:
            from usr.bin.exception_service import ExceptionServiceMonitor
            EXCEPTION = "exception"
            ex_monitor = ExceptionServiceMonitor.create_monitor(self.service_config.get(EXCEPTION, None))
            if ex_monitor is not None:
                monitor_map[EXCEPTION] = ex_monitor
            else:
                raise Exception("exception service load error")
            print("[    OK     ] create app monitor exception service")
        except Exception as e:
            # 异常重定向
            self.error_handler("[   FAILED  ] load exception monitor error reason:[{}]".format(e))

        try:
            from usr.bin.cloud_service import CloudServiceMonitor
            CLOUD = "cloud"
            cd_monitor = CloudServiceMonitor.create_monitor(self.service_config.get(CLOUD, None))
            if cd_monitor is not None:
                monitor_map[CLOUD] = cd_monitor
            else:
                raise Exception("cloud service load error")
            print("[    OK     ] create app monitor cloud service")
        except Exception as e:
            # 异常重定向
            self.error_handler("[   FAILED  ] load cloud monitor error reason:[{}]".format(e))

        try:
            from usr.bin.pm_service import PMServiceMonitor
            PM = "pm"
            pm_monitor = PMServiceMonitor.create_monitor(self.service_config.get(PM, None))
            if pm_monitor is not None:
                monitor_map[PM] = pm_monitor
            else:
                raise Exception("pm service load error")
            print("[    OK     ] create app monitor pm service")
        except Exception as e:
            # 异常重定向
            self.error_handler("[   FAILED  ] load pm monitor error reason:[{}]".format(e))

        return monitor_map

    def version(self):
        return version()
