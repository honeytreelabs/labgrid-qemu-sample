import enum


class Status(enum.Enum):
    unknown = 0
    off = 1
    shell = 2
    internet = 3
    ssh = 4
