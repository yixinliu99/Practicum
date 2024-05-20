from dataclasses import dataclass
from thaw_action.model.ThawStatus import ThawStatus
from thaw_action.utils import get_data_types


@dataclass
class ThawMetadata:
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
        datatypes = get_data_types()
        res = {
            datatypes.ACTION_ID: {'S': self.action_id},
            datatypes.OBJECT_ID: {'S': self.object_id},
            datatypes.THAW_STATUS: {'S': self.thaw_status},
            datatypes.START_TIME: {'S': self.start_time},
            datatypes.EXPIRY_TIME: {'S': self.expiry_time}
        }

        return res

    @staticmethod
    def parse(item):
        res = {}
        for key in item:
            res[key] = item[key]['S']

        return ThawMetadata(**res)
