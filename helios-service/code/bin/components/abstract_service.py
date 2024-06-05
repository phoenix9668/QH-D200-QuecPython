from usr.bin.components.blinker_min import Signal, signal
from event_message import Event, EventManager, EventMessageObject
from usr.bin.components.service_models import QMessageModel, LockMsgModel
import _thread

ANY = "anonymous"


class AbstractService(object):
    def __init__(self, sign):
        self.__name = sign

        self.__signal = signal(sign)

        self.__event = Event(sign)

        self.__em = EventManager()

        self.__message_id = 0

        self.__service_status = 0

        self.__em.register_event(self.__event)

        self.__mode = 1

    def set_mode(self, mode):
        self.__mode = mode

    @property
    def mode(self):
        return self.__mode

    @property
    def name(self):
        return self.__name

    @property
    def message_id(self):
        """return self.next message id."""
        return self.__message_id + 1

    @property
    def signal(self):
        """signal to get by this method"""
        return self.__signal

    def ms_id_increase(self):
        if self.__message_id > 99999:
            self.__message_id = 0
        else:
            self.__message_id += 1
        return self.message_id

    def _get_message(self, sender=None, msg_type=0xFF, message=None, callback=None, lock_msg=None):
        """get message"""
        if callback is not None and not callable(callback):
            return None
        ms_id = self.ms_id_increase()
        qm = QMessageModel(ms_id=ms_id, msg_type=msg_type, message=message, sender=sender, from_event=self.__event.name,
                           lock_msg=lock_msg)
        return qm

    def _callback(self, **kwargs):
        """event callback"""
        em = kwargs.get("event_message", False)
        if em.msg:
            msg = em.msg
            try:
                self.signal.send(em.msg.sender, message=msg())
            except Exception as e:
                success = 0
            else:
                success = 1
            resp_data = dict(message=msg(), success=success)
            if em.callback is not None:
                try:
                    em.callback(**resp_data)
                except Exception as e:
                    pass
            if msg.lock_msg is not None:
                msg.lock_msg.msg = resp_data
                msg.lock_msg.lock.release()

    def _clear(self, *args, **kwargs):
        """ stop crontab task"""
        self.__event.clear()

    def _add_default_handler(self):
        """add default handler"""
        self.add_handler(self._callback)

    def register_event(self):
        """achieve by class extend AbstractService"""
        pass

    def prepare_before_start(self):
        """prepare before start action"""
        pass

    def prepare_before_stop(self):
        """prepare after start action"""
        pass

    def start_crontab(self, *args, **kwargs):
        """achieve by timer task"""
        pass

    def add_handler(self, handler):
        """
        support for scan addition and manual sword
        :param handler: deal handler
        :return:
        """
        self.__event.add_handler(handler)
        return handler

    def add_handler_via(self):
        """
        Support for multiple annotations
        :return:
        """

        def decorator(fn):
            self.add_handler(fn)
            return fn

        return decorator

    def send_msg_async(self, msg_type=0xFF, message=None, callback=None, sender=None):
        if self.status():
            qm = self._get_message(sender=sender, msg_type=msg_type, message=message, callback=callback)
            self.__event.post(qm, callback=callback)
        else:
            return 0

    def send_msg_sync(self, msg_type=0xFF, message=None, callback=None, sender=None):
        if self.status():
            lock = _thread.allocate_lock()
            lock_msg = LockMsgModel(lock)
            qm = self._get_message(sender=sender, msg_type=msg_type, message=message, callback=callback,
                                   lock_msg=lock_msg)
            self.__event.post(qm, callback=callback)
            lock_msg.lock.acquire()
            msg = lock_msg.msg
            del lock_msg
            return msg
        else:
            return 0

    def send_msg(self, msg_type=0xFF, message=None, callback=None, sender=None, mode=None):
        mode_pattern = self.mode
        if mode is not None:
            mode_pattern = mode
        if mode_pattern:
            return self.send_msg_async(msg_type=msg_type, message=message, callback=callback, sender=sender)
        else:
            return self.send_msg_sync(msg_type=msg_type, message=message, callback=callback, sender=sender)

    def _component_start(self):
        """start components"""
        if not self.__service_status:
            self.register_event()
            self._add_default_handler()
            self.prepare_before_start()
            self.start_crontab()

    def start(self):
        """
        start the service
        :return: 1 or 0
        """
        self._component_start()
        self.__service_status = self.__em.start()
        return self.__service_status

    def status(self):
        """
        status of service
        :return:
        """
        return self.__em.status

    def stop(self):
        """
        stop the service
        :return:
        """
        self.prepare_before_stop()
        self.__service_status = self.__em.stop()
        return self.__service_status

    def close(self):
        self._clear()

    def subscribe(self, cb, sender=ANY):
        self.signal.connect(cb, sender=sender)

    def unsubscribe(self, cb, sender=ANY):
        self.signal.disconnect(cb, sender=sender)

    def publish(self, msg, sender=ANY, msg_type=0XFF):
        self.send_msg(message=msg, msg_type=msg_type, sender=sender)
