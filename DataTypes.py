class DataTypes:
    def __init__(self, OBJECTS_STATUS_TABLE_NAME, ACTION_STATUS_TABLE_NAME, REGION_NAME, SNS_TOPIC_ARN, GSI_INDEX_NAME, **kwargs):
        self.THAW_STATUS = 'thaw_status'
        self.ACTION_ID = 'action_id'
        self.OBJECT_ID = 'object_id'
        self.START_TIME = 'start_time'
        self.EXPIRY_TIME = 'expiry_time'
        self.GLACIER = 'GLACIER'
        self.DEEP_ARCHIVE = 'DEEP_ARCHIVE'
        self.INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
        self.ARCHIVE_CLASSES = [self.GLACIER, self.DEEP_ARCHIVE, self.INTELLIGENT_TIERING]
        self.OBJECTS_STATUS_TABLE_NAME = OBJECTS_STATUS_TABLE_NAME
        self.ACTION_STATUS_TABLE_NAME = ACTION_STATUS_TABLE_NAME
        self.REGION_NAME = REGION_NAME
        self.SNS_TOPIC_ARN = SNS_TOPIC_ARN
        self.GSI_INDEX_NAME = GSI_INDEX_NAME
