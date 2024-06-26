class DataTypes:
    def __init__(self, params):
        self.THAW_STATUS = 'thaw_status'
        self.ACTION_ID = 'action_id'
        self.OBJECT_ID = 'object_id'
        self.START_TIME = 'start_time'
        self.EXPIRY_TIME = 'expiry_time'
        self.BUCKET_NAME = 'bucket_name'
        self.GLACIER = 'GLACIER'
        self.DEEP_ARCHIVE = 'DEEP_ARCHIVE'
        self.INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
        self.ARCHIVE_CLASSES = [self.GLACIER, self.DEEP_ARCHIVE, self.INTELLIGENT_TIERING]
        self.OBJECTS_STATUS_TABLE_NAME = params['OBJECTS_STATUS_TABLE_NAME']
        self.ACTION_STATUS_TABLE_NAME = params['ACTION_STATUS_TABLE_NAME']
        self.REGION_NAME = params['REGION_NAME']
        self.SNS_TOPIC_ARN = params['SNS_TOPIC_ARN']
        self.ACTION_STATUS_GSI_INDEX_NAME = params['ACTION_STATUS_GSI_INDEX_NAME']
        self.BUCKET_GSI_INDEX_NAME = params['BUCKET_GSI_INDEX_NAME']
        self.S3_QUERY_INTERVAL = int(params['S3_QUERY_INTERVAL'])
        self.APT_CLIENT_ID = params['APT_CLIENT_ID']
        self.APT_CLIENT_SECRET = params['APT_CLIENT_SECRET']
