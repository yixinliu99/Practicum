from dataclasses import dataclass
from thaw_action.model.ThawStatus import ThawStatus


@dataclass
class ThawMetadata:
    THAW_STATUS = 'thaw_status'
    ACTION_ID = 'action_id'
    OBJECT_ID = 'object_id'
    START_TIME = 'start_time'
    EXPIRY_TIME = 'expiry_time'

    action_id: str
    object_id: str
    thaw_status: ThawStatus
    start_time: str
    expiry_time: str

    def __init__(self, action_id, object_id, thaw_status: ThawStatus, start_time, expiry_time):
        if not action_id:
            raise ValueError('action_id is required')
        if not object_id:
            raise ValueError('object_id is required')
        if not thaw_status:
            raise ValueError('status is required')

        self.action_id = action_id
        self.object_id = object_id
        self.thaw_status = thaw_status
        self.start_time = start_time if start_time else ''
        self.expiry_time = expiry_time if expiry_time else ''

    def marshal(self):
        res = {
             self.ACTION_ID: {'S': self.action_id},
             self.OBJECT_ID: {'S': self.object_id},
             self.THAW_STATUS: {'S': self.thaw_status},
             self.START_TIME: {'S': self.start_time},
             self.EXPIRY_TIME: {'S': self.expiry_time}
        }

        return res

    @staticmethod
    def parse(item):
        res = {}
        for key in item:
            res[key] = item[key]['S']

        return ThawMetadata(**res)
