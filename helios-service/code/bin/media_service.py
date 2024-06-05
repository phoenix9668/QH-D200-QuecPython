from usr.bin.components.abstract_service import AbstractService
from usr.bin.components.monitor import ServiceMonitor
import audio
import utime

MEDIA = "MEDIA"
MEDIA_TYPE_MAP = {
    "AUDIO": 0,
    "TTS": 1
}


class MediaServiceMonitor(ServiceMonitor):

    @staticmethod
    def create_monitor(config=None):
        media_service = MediaService()
        if config is not None:
            try:
                if config.get('enable', True):
                    mode = config["params"]["mode"]
                    return MediaServiceMonitor(media_service)
            except Exception as e:
                # 这里异常重定向
                return None
        msm = MediaServiceMonitor(media_service)
        if config is not None:
            msm.set_exception_handlers(config.get('exceptionHandlers', None))
        return msm


class MediaService(AbstractService):

    def __init__(self, device=0):
        super().__init__(MEDIA)
        self.__tts = audio.TTS(device)
        self.__audio = audio.Audio(device)

    def set_tts(self, mode):
        self.__tts = audio.TTS(mode)

    def set_audio(self, mode):
        self.__audio = audio.Audio(mode)

    def set_pa(self, pa):
        return self.__audio.set_pa(pa)

    def set_mode(self, mode):
        if mode in range(0x03):
            self.set_audio(mode)
            self.set_tts(mode)
        else:
            raise Exception("mode {} must in mid of [0,1,2]".format(mode))

    @property
    def tts(self):
        return self.__tts

    @property
    def audio(self):
        return self.__audio

    def _play(self, sender, **kwargs):
        msg_type = kwargs["message"]['msg_type']
        msg = kwargs["message"]['message']
        # 策略
        ret = self.__start_play(msg_type, msg)

        while ret == -2:
            print(ret, msg)
            ret = self.__start_play(msg_type, msg)
            utime.sleep(1)

    def __start_play(self, msg_type, msg):
        if msg_type == MEDIA_TYPE_MAP["TTS"]:
            ret = self.__tts.play(msg["priority"], msg["breakin"], msg["mode"], msg['play_data'])
        else:
            ret = self.__audio.play(msg["priority"], msg["breakin"], msg['play_data'])
        return ret

    def tts_play(self, priority=4, breakin=0, mode=2, play_data="", sender=None):
        message = dict(priority=priority, breakin=breakin, mode=mode, play_data=play_data)
        self.send_msg(msg_type=MEDIA_TYPE_MAP["TTS"], sender=sender, message=message)

    def audio_play(self, priority=4, breakin=0, play_data="", sender=None):
        message = dict(priority=priority, breakin=breakin, play_data=play_data)
        self.send_msg(msg_type=MEDIA_TYPE_MAP["AUDIO"], sender=sender, message=message)

    def register_event(self):
        super().register_event()
        self.signal.connect(self._play, sender="anonymous")


if __name__ == '__main__':
    media = MediaService()
    media.start()
    media.audio.setVolume(2)
    media.tts_play(play_data="123")
