ANY = "anonymous"


class Signal(object):

    def __init__(self, doc):
        self.receivers = {
            ANY: list()
        }
        self.doc = doc

    def connect(self, receiver, sender=ANY):
        if sender not in self.receivers:
            self.receivers[sender] = list()
        self.receivers[sender].append(receiver)

    def connect_via(self, sender=ANY):
        def decorator(fn):
            self.connect(fn, sender)
            return fn

        return decorator

    def receivers_for(self, sender):
        return self.receivers.get(sender, [])

    def send(self, *senders, **kwargs):
        if not len(senders):
            senders = list(ANY)
        for sender in senders:
            self.__publish(sender, **kwargs)

    def __publish(self, sender, **kwargs):
        for receiver in self.receivers_for(sender):
            try:
                receiver(sender, **kwargs)
            except Exception as e:
                print("send to {} kwargs error, reason {}".format(sender, kwargs))

    def disconnect(self, receiver, sender=ANY):
        receivers = self.receivers_for(sender)
        receivers.remove(receiver)


class NamedSignal(Signal):

    def __init__(self, name, doc=None):
        super().__init__(doc)
        self.name = name


class Namespace(dict):

    def signal(self, name, doc=None):
        try:
            return self[name]
        except KeyError:
            return self.setdefault(name, NamedSignal(name, doc))


signal = Namespace().signal
