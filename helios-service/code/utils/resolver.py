import utime


class TimeResolver(object):

    def __init__(self):
        self.output_format = "{ascdate} {asctime} {ascweek}"
        self.weekday_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def resolver(self, rt=None):
        if rt is None:
            rt = utime.localtime()
        d_f = "{0:02}"
        return self.output_format.format(
            ascdate=str(rt[0]) + "-" + d_f.format(rt[1]) + "-" + d_f.format(rt[2])
            , asctime=d_f.format(rt[3]) + ":" + d_f.format(rt[4]) + ":" + d_f.format(rt[5]),
            ascweek=self.weekday_list[rt[6]])


if __name__ == '__main__':
    print(TimeResolver().resolver())
