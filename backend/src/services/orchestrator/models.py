from enum import Enum


class ResponseMode(str, Enum):
    LEARN = "learn"
    REVISION = "revision"
    PRELIMS = "prelims"
    MAINS = "mains"
    INTERVIEW = "interview"