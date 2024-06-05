try:
    import uos as os
    import utime as time
    import ujson as json
except:
    import os
    import time
    import json


def Singleton(cls):
    _instance = {}

    def _singleton(*args, **kargs):
        if cls not in _instance:
            _instance[cls] = cls(*args, **kargs)
        return _instance[cls]

    return _singleton


@Singleton
class OfflineStorage:

    def __init__(self):
        self.status = None
        self.split_file = False
        self.single_file_max = 100
        self._file_name_no = 1
        self._rec_count = 1
        # self.default_dir = "/usr/offline_storage/"
        self.default_dir = "./"
        self._check_dir()

    def _check_dir(self):
        try:
            os.chdir(self.default_dir)
        except:
            raise SystemError("Directory is not exist!")

    @staticmethod
    def _msg_no_gen():
        # ts = time.time()
        ts = int(time.time())
        ts_str = str(ts)
        if len(ts_str) > 5:
            ts = int(ts_str[-5:])
        # 避免时间戳生成时间太短导致重复
        time.sleep(1)
        return ts

    def _get_file_list(self):
        file_list = os.listdir(self.default_dir)
        file_list.sort()
        # 筛选后缀名
        file_filtered = []
        for file in file_list:
            try:
                if file[-5:] == ".json":
                    file_filtered.append(file)
            except:
                continue
        return file_filtered

    def _pre_load(self):
        # 预读取
        data_map = dict()
        file_list = self._get_file_list()
        if not file_list:
            return data_map
        file = file_list.pop()
        with open(self.default_dir + file, 'r', encoding="utf-8") as f:
            try:
                file_map = json.load(f)
            except:
                file_map = dict()
            self._rec_count = len(file_map.keys())
            data_map.update(file_map)
        return data_map

    def _write_file(self, data):
        file_list = self._get_file_list()
        file_list.sort()
        if not file_list:
            if self.split_file:
                if self._rec_count > self.single_file_max:
                    self._file_name_no += 1
                file_name = "data%d.json" % self._file_name_no
            else:
                file_name = "data.json"
        else:
            file_name = file_list.pop()
        with open(self.default_dir+file_name, "w+", encoding="utf-8") as f:
            json.dump(data, f)
        self._rec_count += 1

    def deposit(self, data):
        if self.status == 'r':
            return False
        self.status = 'w'
        # 序号生成
        index = self._msg_no_gen()
        format_data = {index: data}
        data_map = self._pre_load()
        data_map.update(format_data)
        self._write_file(data_map)
        self.status = None
        return index

    def take_out(self):
        if self.status == 'w':
            return False
        self.status = 'r'
        file_list = self._get_file_list()
        if not file_list:
            return False
        file_list.sort()
        data_map = dict()
        for file in file_list:
            with open(self.default_dir + file, 'r', encoding="utf-8") as f:
                try:
                    data_map.update(json.load(f))
                except:
                    pass
            os.remove(self.default_dir + file)
        self.status = None
        return data_map

    def take_out_iter(self):
        data_map = self.take_out()
        for k, v in data_map.items():
            yield k, v

    def take_out_list(self):
        data_map = self.take_out()
        return list(data_map.values())

    def take_out_by_index(self, index):
        if self.status == 'w':
            return False
        self.status = 'r'
        file_list = self._get_file_list()
        if not file_list:
            return None
        file_list.sort()
        for file in file_list:
            with open(self.default_dir + file, 'r+', encoding="utf-8") as f:
                file_map = json.load(f)
                if index in file_map:
                    data = file_map.pop(index)
                    json.dump(file_map, f)
                    return data
        return None

    def take_out_last(self, count=1):
        if self.status == 'w':
            return False
        self.status = 'r'
        file_list = self._get_file_list()
        if not file_list:
            return None
        file_list.sort(reverse=True)
        take_out_count = 0
        data_map = dict()
        for file in file_list:
            with open(self.default_dir + file, 'r+', encoding="utf-8") as f:
                file_map = json.load(f)
                items = sorted(file_map.items())
                while take_out_count <= count and items:
                    key, values = items.pop()
                    data_map[key] = values
                    file_map.pop(key)
                json.dump(file_map, f)
            if not items:
                os.remove(self.default_dir + file)
        return data_map

    def count(self):
        file_list = self._get_file_list()
        data_count = 0
        for file in file_list:
            with open(self.default_dir + file, 'r', encoding="utf-8") as f:
                try:
                    data_count += len(json.load(f))
                except:
                    pass
        return data_count

    def preview_data(self):
        data_map = dict()
        file_list = self._get_file_list()
        if not file_list:
            return data_map
        file_list.sort()
        for file in file_list:
            with open(self.default_dir + file, 'r', encoding="utf-8") as f:
                try:
                    data_map.update(json.load(f))
                except:
                    pass
        return data_map

