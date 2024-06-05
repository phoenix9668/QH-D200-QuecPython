from usr.bin.components.abstract_service import AbstractService
from usr.utils.service_utils import Singleton
from usr.bin.components.monitor import ServiceMonitor
import dataCall
import net
import sim
import checkNet

__all__ = ["NetService"]
NET = "NET"

ENABLE_ = "enable"
NET_ = "NET"
DATACALL_ = "DATACALL"


class NetServiceMonitor(ServiceMonitor):

    @staticmethod
    def create_monitor(config=None):
        net_service = NetService()
        nsm = NetServiceMonitor(net_service)
        if config is not None:
            nsm.set_exception_handlers(config.get('exceptionHandlers', None))
        return nsm


@Singleton
class NetService(AbstractService):
    def __init__(self):
        super().__init__(NET)

        self.__data_call = dataCall

        self.__net = net

        self.__sim = sim

        self.__net_connect_status = False

        self.__data_call_status = False

        self.server_status = {
            DATACALL_: {ENABLE_: 1},
            NET_: {ENABLE_: 0}
        }
        self.check_net = checkNet.CheckNetwork("QuecPython_Helios_Framework", "this latest version")

    @property
    def sim(self):
        return self.__sim

    @property
    def data_call(self):
        return self.__data_call

    @property
    def net(self):
        return self.__net

    def set_enable(self, sr, enable):
        """set start"""
        self.server_status[sr][ENABLE_] = enable

    def set_apn(self, profileIdx, ipType, apn, username, password, authType):
        return self.__data_call.setApn(profileIdx, ipType, apn, username, password, authType)

    def ev_dc(self, args):
        if self.server_status[DATACALL_][ENABLE_]:
            profile_idx = args[0]
            datacall_status = args[1]

            msg_dict = \
                {
                    "sim_status": None,
                    "net_status": None,
                    "datacall_status": datacall_status,
                    "profile_id": profile_idx,
                    "ip_type": None,
                    "IPv4": None,
                    "IPv4_DNS1": None,
                    "IPv4_DNS2": None,
                    "IPv6": None,
                    "IPv6_DNS1": None,
                    "IPv6_DNS2": None,
                }

            sim_status = self.__sim.getStatus()
            net_status = self.__net.getState()
            datacall_info = self.__data_call.getInfo(profile_idx, 2)

            msg_dict.update({"sim_status": sim_status})

            if net_status != -1:
                if net_status[0][0] == 0 or net_status[1][0] == 0:
                    msg_dict.update({"net_status": 0})
                else:
                    msg_dict.update({"net_status": net_status[1][0]})
            else:
                msg_dict.update({"net_status": -1})
            if datacall_info != -1:
                if datacall_info[2][0] == 1 or datacall_info[3][0] == 1:
                    msg_dict.update({"datacall_status": 1})
                else:
                    msg_dict.update({"datacall_status": 0})
                msg_dict.update({"ip_type": datacall_info[1]})
                msg_dict.update({"IPv4": datacall_info[2][2]})
                msg_dict.update({"IPv4_DNS1": datacall_info[2][3]})
                msg_dict.update({"IPv4_DNS2": datacall_info[2][4]})
                msg_dict.update({"IPv6": datacall_info[3][2]})
                msg_dict.update({"IPv6_DNS1": datacall_info[3][3]})
                msg_dict.update({"IPv6_DNS2": datacall_info[3][4]})
            self.send_msg(msg_type=1, message=msg_dict)

    def ev_nc(self, args):
        if self.server_status[NET_][ENABLE_]:
            net_status = args[1]
            self.send_msg(msg_type=0, message={"network_register_status": net_status})

    def wait_connect(self, timeout):
        self.check_net.poweron_print_once()
        return self.check_net.wait_network_connected(timeout)

    def get_net_status(self):
        self.__data_call_status = self.__data_call.getInfo(1, 0)[2][0]
        return self.__data_call_status

    def register_event(self):
        self.__data_call.setCallback(self.ev_dc)
        # self.__net.setCallback(self.ev_nc)


if __name__ == '__main__':
    net_ser = NetService()


    @net_ser.signal.connect_via(0X01)
    def test(*args, **kwargs):
        print(kwargs)


    net_ser.start()
    net_ser.send(sender=1, message={})
