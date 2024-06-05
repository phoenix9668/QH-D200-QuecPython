import modem, ubinascii, net, uhashlib, request, ujson, app_fota, fota, utime, uos, log
from misc import Power
from unzip import UnZipUtils
from app_fota_download import update_download_stat, delete_update_file

PROCESS_CODE = {
    "DO_NOT_UPGRADE": 0,
    "DOWNLOADING_FIRMWARE": 3,
    "DOWNLOADED_NOTIFY_UPDATE": 4,
    "DOWNLOAD_FAILED": 5,
    "UPDATE_START": 6,
    "UPGRADE_SUCCESS": 7,
    "UPGRADE_FAILED": 8,
}
USR = "/usr/"
CONFIG_PATH = "ota_config.json"
MAIN_PY = "main.py"
BIN_MODE = "0"
APP_MODE = "1"
UPDATER_DIR = '/usr/.updater'
# 后续版本支持批量升级
# BULK_APP_MODE = "2"
log.basicConfig(level=log.INFO)
ota_log = log.getLogger("ota")
fota_bin_file = "FotaFile.bin"
MODE_MAP = {
    BIN_MODE: "_upgrade_fota_bin",
    APP_MODE: "_upgrade_fota_sh",
    # 后续支持BULK升级
    # BULK_APP_MODE: "_upgrade_fota_bulk_sh",
}
ZIP = ".zip"


class RET:
    OK = "20000"
    # 系统组件错误
    UPGRADE = "3001"
    NOUPGRADE = "3002"
    # 网络协议错误
    TOKENERR = "4001"
    GETUPGRADEURLERR = "4002"
    DOWNLOADERR = "4003"
    PARAMSERR = "4004"
    MODENOTEXIST = "4005"
    FOTAVERIFAILD = "4006"
    COMMIT_LOG_ERROR = "4007"
    # 配置错误
    SAVECONFIGERR = "4021"
    GETCONFIGERR = "4022"
    NETERR = "4023"
    REQERR = "4024"
    WIOERR = "4025"
    FWSTREAMERR = "4026"
    RIOERR = "4027"
    UNZIPERROR = "4028"
    UNZIPFILEPROTOCOLERROR = "4029"


error_map = {
    RET.OK: u"成功",
    # 系统
    RET.UPGRADE: u"有升级计刿",
    RET.NOUPGRADE: u"无升级计刿",
    # 协议
    RET.TOKENERR: u"获取token失败",
    RET.GETUPGRADEURLERR: u"获取升级地址失败",
    RET.DOWNLOADERR: u"下载固件失败",
    RET.PARAMSERR: u"参数获取失败",
    RET.MODENOTEXIST: u"模式不存圿",
    ###
    RET.SAVECONFIGERR: u"保存配置错误",
    RET.GETCONFIGERR: u"获取配置错误",
    RET.NETERR: u"网络错误",
    RET.WIOERR: u"文件写错诿",
    RET.FWSTREAMERR: u"FOTA字节流作牿",
    RET.RIOERR: u"文件读错诿",
    RET.UNZIPERROR: u"文件解压失败",
    RET.UNZIPFILEPROTOCOLERROR: u"压缩文件解析失败",
}


class OTAUtil(object):
    @classmethod
    def rm_upgrade_file(cls, file_name):
        uos.remove(UPDATER_DIR + file_name)
        delete_update_file(file_name)

    @classmethod
    def add_upgrade_file(cls, url, file_name):
        update_download_stat(url, USR + file_name, uos.stat(UPDATER_DIR + USR + file_name)[6])


class UCloudOTA(object):

    def __init__(self, battery=100, url="https://cloudota.quectel.com:8100/v1"):
        self.imei = modem.getDevImei()
        self.rsrp = net.csqQueryPoll()
        self.url = url
        self.module_type = ""
        self.battery = battery
        self.version = ""
        self.uid = ""
        self.pk = ""
        self.cellId = ""
        self.mnc = ""
        self.mcc = ""
        self.lac = ""
        self.report_url = "/fota/status/report"
        self.access_token = ""
        self.upgrade_info = {}
        self.bin_path = "/usr/FotaFile.bin"
        self.ota_config_info = {
            "version": "V1.0.0",
            "flag": "0",
            "fw_version": modem.getDevFwVersion()
        }
        self.info_map = {
            APP_MODE: {
                "reboot": True,
                "uid": "",
                "pk": ""
            },
            BIN_MODE: {
                "reboot": True,
                "uid": "",
                "pk": ""
            }
        }

    def _upgrade_fota(self, mode):
        "升级fota bin"
        try:
            action = self.upgrade_info["action"]
            url = self.upgrade_info["url"]
        except Exception as e:
            return RET.PARAMSERR
        try:
            if action:
                self.report("DOWNLOADING_FIRMWARE")
                if mode == APP_MODE:
                    if url.endswith(ZIP):
                        # APP 升级
                        code = self._upgrade_fota_bulk_sh(url)
                        if code != RET.OK:
                            return code
                    else:
                        self._upgrade_fota_sh(url)
                    if self.info_map[APP_MODE]["reboot"]:
                        self.power_restart()
                elif mode == BIN_MODE:
                    # fota 升级
                    self._upgrade_fota_bin(url)
                    ota_log.info("self.info_map[BIN_MODE][reboot] === {}".format(self.info_map[BIN_MODE]["reboot"]))
                    if self.info_map[BIN_MODE]["reboot"]:
                        self.power_restart()
                else:
                    # 模式 不匹酿
                    return RET.MODENOTEXIST
                self.report("DOWNLOADED_NOTIFY_UPDATE")
                return RET.UPGRADE
            else:
                self.report("DO_NOT_UPGRADE")
                return RET.NOUPGRADE
        except Exception as e:
            ota_log.error(e)
            self.report(PROCESS_CODE[5])
            return RET.DOWNLOADERR

    def _upgrade_fota_bulk_sh(self, url):
        """
        批量升级
        :param url:
        :return:
        """
        zip_file = url.split("/")[-1]
        fota = app_fota.new()
        fota.download(url, USR + zip_file)
        zip_util = UnZipUtils(dest_dir=UPDATER_DIR + USR)
        try:
            zip_util.set_data(zip_file)
        except Exception as e:
            ota_log.error(e)
            return RET.UNZIPERROR

        try:
            code = zip_util.run()
            if not code:
                return code
        except Exception as e:
            return RET.UNZIPFILEPROTOCOLERROR
        for file_name in zip_util.file_name_list:
            OTAUtil.add_upgrade_file(url, file_name)
        OTAUtil.rm_upgrade_file(USR + zip_file)
        self.report("DOWNLOADED_NOTIFY_UPDATE")
        fota.set_update_flag()
        try:
            self.ota_config_info["version"] = self.upgrade_info["targetVersion"]
            self.ota_config_info["flag"] = "1"
            with open(USR + CONFIG_PATH, "w") as f:
                f.write(ujson.dumps(self.ota_config_info))
        except Exception as e:
            ota_log.info(e)
        self.report("UPDATE_START")
        return RET.OK

    def _upgrade_fota_sh(self, url):
        """
        升级单个脚本
        :param cover_file: 升级后覆盖的文件
        :return:
        """
        zip_file = url.split("/")[-1]
        fota = app_fota.new()
        # 覆盖cover_file
        cover_file = USR + zip_file[zip_file.find("_") + 1:]
        fota.download(url, cover_file)
        self.report("DOWNLOADED_NOTIFY_UPDATE")
        fota.set_update_flag()
        try:
            self.ota_config_info["version"] = self.upgrade_info["targetVersion"]
            self.ota_config_info["flag"] = "1"
            with open(USR + CONFIG_PATH, "w") as f:
                f.write(ujson.dumps(self.ota_config_info))
        except Exception as e:
            ota_log.info(e)
        self.report("UPDATE_START")

    def _upgrade_fota_bin(self, url):
        self.report("DOWNLOADED_NOTIFY_UPDATE")
        try:
            r = request.get(url, sizeof=4096)
        except Exception as e:
            return RET.REQERR
        if r.status_code == 200 or r.status_code == 206:
            file_size = int(r.headers['Content-Length'])
            fota_obj = fota()
            count = 0
            try:
                while True:
                    c = next(r.content)
                    length = len(c)
                    for i in range(0, length, 4096):
                        count += len(c[i:i + 4096])
                        fota_obj.write(c[i:i + 4096], file_size)
            except StopIteration:
                r.close()
            except Exception as e:
                r.close()
                return RET.FWSTREAMERR
            else:
                r.close()
            res = fota_obj.verify()
            if res != 0:
                return RET.FOTAVERIFAILD
            self.report("DOWNLOADED_NOTIFY_UPDATE")
            return RET.OK
        else:
            return RET.REQERR

    def _upgrade_template(self, mode, module_type="", version=""):
        """
        开启固件脚本升级方弿
        :return: STATE
        """
        self.module_type = modem.getDevFwVersion()[:5] if not module_type else module_type

        # 判斷模式
        if mode == APP_MODE:
            state = self.register_upgrade_sh(version=version)
            ota_log.info("the device app currently version is {}".format(self.version))
        elif mode == BIN_MODE:
            state = self.register_upgrade_bin()
            ota_log.info("the device fireware currently version is {}".format(self.version))
        else:
            return RET.MODENOTEXIST
        # 注册upgrade sh
        if state != RET.OK:
            return state
        # 升级脚本
        state = self.get_upgrade_url(mode)
        if state != RET.OK:
            return state
        # 升级脚本
        state = self._upgrade_fota(mode)
        return state

    def get_token(self, prefix="/oauth/token", kwargs=None):
        # 获取token
        if net.csqQueryPoll() == 99 or net.csqQueryPoll() == -1:
            return RET.NETERR
        uri = self.url + prefix
        try:
            secret = ubinascii.hexlify(uhashlib.md5("QUEC" + str(self.imei) + "TEL").digest())
            secret = secret.decode()
            uri = uri + "?imei=" + self.imei + "&" + "secret=" + secret
            ota_log.info("uri = {}".format(uri))
            resp = request.get(uri)
            json_data = resp.json()
            ota_log.info("get_token = {}".format(json_data))
            self.access_token = json_data["data"]["access_Token"]
            return RET.OK
        except Exception as e:
            ota_log.error("get_token error:{}".format(e))
            return RET.TOKENERR

    def report(self, code, msg=None):
        data_info = {
            "version": str(self.version),
            "ver": "v1.0",
            "imei": str(self.imei),
            "code": PROCESS_CODE.get(code, 0),
            "msg": str(msg) if msg else code
        }

        ota_log.info(data_info)

        uri = self.url + self.report_url

        headers = {"access_token": self.access_token, "Content-Type": "application/json"}
        try:
            resp = request.post(uri, data=ujson.dumps(data_info), headers=headers)
            return resp
        except Exception as e:
            return -1

    def get_upgrade_url(self, mode, prefix="/fota/fw"):
        ota_log.info("module_type == {}".format(self.module_type))
        params = "?" + "version=" + str(self.version) + "&" + "imei=" + str(self.imei) + "&" + "moduleType=" + str(
            self.module_type) + "&" + "battery=" + str(
            self.battery) + "&" + "rsrp=" + str(
            self.rsrp) + "&" + "uid=" + str(
            self.info_map[mode]["uid"]) + "&" + "pk=" + str(
            self.info_map[mode]["pk"])
        ota_log.info(params)
        uri = self.url + prefix + params
        headers = dict(access_token=self.access_token)
        try:
            resp = request.get(uri, headers=headers)
            json_data = resp.json()
            ota_log.info("get_upgrade_url json data {}".format(json_data))
            if json_data["code"] == 200:
                self.upgrade_info = json_data
                return RET.OK
            else:
                ota_log.info("no upgrade plan for this device")
                return RET.NOUPGRADE
        except Exception as e:
            ota_log.info("get_upgrade_url {}".format(e))
            return RET.GETUPGRADEURLERR

    def _register_upgrade(self, mode, version=""):
        """
        注册脚本升级
        :param version:版本叿
        :return:
        """
        try:
            list_dirs = uos.listdir(USR)
            if CONFIG_PATH in list_dirs:

                with open(USR + CONFIG_PATH, "r") as f:
                    self.ota_config_info = ujson.loads(f.read())
            else:
                if mode == APP_MODE:
                    # 应用检测版本号
                    if version:
                        self.ota_config_info["version"] = version
                with open(USR + CONFIG_PATH, "w") as f:
                    f.write(ujson.dumps(self.ota_config_info))
        except Exception as e:
            ota_log.error("register_upgrade_sh = {}".format(e))
            # 读写config 错误
            return RET.GETCONFIGERR

        # 获取token
        state = self.get_token()
        if state != RET.OK:
            return state

        try:
            if mode == APP_MODE:
                # app mode
                self.version = self.ota_config_info["version"]
                if self.ota_config_info["flag"] == "1":
                    # 升级成功
                    self.report("UPGRADE_SUCCESS", self.ota_config_info["version"])
                    self.ota_config_info["flag"] = "0"
                    with open(USR + CONFIG_PATH, "w") as f:
                        f.write(ujson.dumps(self.ota_config_info))
            elif mode == BIN_MODE:
                # bin mode
                self.version = modem.getDevFwVersion()
                if self.ota_config_info["fw_version"] != self.version:
                    # OTA升级成功
                    self.report("UPGRADE_SUCCESS", self.version)
                    self.ota_config_info['fw_version'] = self.version
                    with open(USR + CONFIG_PATH, "w") as f:
                        f.write(ujson.dumps(self.ota_config_info))
            else:
                return RET.MODENOTEXIST
            return RET.OK
        except Exception as e:
            return RET.SAVECONFIGERR

    def register_upgrade_sh(self, version=""):
        return self._register_upgrade(APP_MODE, version=version)

    def register_upgrade_bin(self):
        return self._register_upgrade(BIN_MODE)

    def start_upgrade_sh_event(self, module_type, uid, pk, version="", reboot=True):
        """
        开启固件脚本升级方弿
        :return: STATE
        """
        self.info_map[APP_MODE]["reboot"] = reboot
        self.info_map[APP_MODE]["uid"] = uid
        self.info_map[APP_MODE]["pk"] = pk
        return self._upgrade_template(APP_MODE, module_type=module_type, version=version)

    def start_upgrade_bin_event(self, module_type, uid, pk, reboot=True):
        """
        开启固件升级方弿
        :return: STATE
        """
        # 升级脚本
        self.info_map[BIN_MODE]["reboot"] = reboot
        self.info_map[BIN_MODE]["uid"] = uid
        self.info_map[BIN_MODE]["pk"] = pk
        return self._upgrade_template(BIN_MODE, module_type=module_type)

    def power_restart(self):
        """
        重启前的动作
        重启设备
        :return:
        """
        self.power_restart_before()
        Power.powerRestart()

    def power_restart_before(self):
        """
        定义重启的动使
        :return:
        """
        pass

    def commit_log(self, pk, message, battery=100, prefix="/fota/msg/report"):
        v2_url = self.url[:-2] + "v2"
        access_token = self.__get_v2_token(pk, v2_url)
        if access_token == RET.TOKENERR:
            return RET.TOKENERR
        try:
            cl = net.getCellInfo()[2][0]
            data_info = {
                "imei": self.imei,
                "version": self.ota_config_info["version"],
                "reportMsg": str(message),
                "battery": battery,
                "signalStrength": net.csqQueryPoll(),
                "cellInfos": [
                    {
                        "lac": cl[5],
                        "mcc": str(cl[2]),
                        "mnc": str(cl[3]),
                        "cid": cl[1],
                        "signalStrength": net.csqQueryPoll(),
                    }
                ]
            }
            headers = {
                "access_token": access_token,
                "Content-Type": "application/json"
            }
            resp = request.post(self.url + prefix, data=ujson.dumps(data_info),
                                headers=headers)
            return resp.json()
        except Exception as e:
            ota_log.info("commit_log exception {}".format(e))
            return RET.COMMIT_LOG_ERROR

    def __get_v2_token(self, pk, v2_url, prefix="/oauth/token"):
        # 获取token
        if net.csqQueryPoll() == 99 or net.csqQueryPoll() == -1:
            return RET.NETERR
        uri = v2_url + prefix
        try:
            uri = uri + "?imei=" + self.imei + "&" + "pk=" + pk + "&" + "grantType=1"
            ota_log.info("uri = {}".format(uri))
            resp = request.get(uri)
            json_data = resp.json()
            ota_log.info("get_v2_token = {}".format(json_data))
            access_token = json_data["data"]["access_Token"]
            return access_token
        except Exception as e:
            ota_log.error("get_v2_token error:{}".format(e))
            return RET.TOKENERR

