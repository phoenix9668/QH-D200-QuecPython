import uos
import ujson


class Parse(object):
    def parse(self, *args, **kwargs):
        """parse interface"""


class JsonParser(object):
    DEFAULT_FILE_NAME = "config.json"

    @classmethod
    def composite_url(cls, url):
        if not url.endswith("/"):
            url += "/"
        return url + cls.DEFAULT_FILE_NAME

    @classmethod
    def parse(cls, url):
        rep_d = dict(
            status=1,
            data=dict()
        )
        try:
            url = cls.composite_url(url)
            with open(url, "r") as f:
                rep_d["data"] = ujson.load(f)
        except Exception as e:
            rep_d["status"] = 0
            return rep_d
        else:
            return rep_d
