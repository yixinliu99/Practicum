from dataclasses import dataclass
from model.ThawStatus import ThawStatus
import json


@dataclass
class ThawMetadata:
    action_id: str
    object_id: str
    status: ThawStatus
    start_time: str
    completion_time: str
    expiration_time: str

    def __init__(self, action_id, object_id, status: ThawStatus, start_time, completion_time, expiration_time):
        if not action_id:
            raise ValueError('action_id is required')
        if not object_id:
            raise ValueError('object_id is required')
        if not status:
            raise ValueError('status is required')

        self.action_id = action_id
        self.object_id = object_id
        self.status = status
        self.start_time = start_time if start_time else ''
        self.completion_time = completion_time if completion_time else ''
        self.expiration_time = expiration_time if expiration_time else ''

    def marshal(self):
        res = {
            'action_id': {'S': self.action_id},
            'object_id': {'S': self.object_id},
            'status': {'S': self.status},
            'start_time': {'S': self.start_time},
            'completion_time': {'S': self.completion_time},
            'expiration_time': {'S': self.expiration_time}
        }

        return res

    @staticmethod
    def parse(item):
        res = {}
        for key in item:
            res[key] = item[key]['S']

        return ThawMetadata(**res)
