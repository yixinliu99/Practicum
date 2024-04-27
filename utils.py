import boto3

GLACIER = 'GLACIER'
DEEP_ARCHIVE = 'DEEP_ARCHIVE'
INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
ARCHIVE_CLASSES = [GLACIER, DEEP_ARCHIVE, INTELLIGENT_TIERING]


def thaw_objects(complete_path, action_id):
    s3 = boto3.client('s3')
    dynamodb = boto3.client('dynamodb')
    source_bucket = complete_path.split('/')[0]
    name = '/'.join(complete_path.split('/')[1:])
    print(complete_path)
    print(source_bucket)
    print(name)
    list_objects = s3.list_objects_v2(Bucket=source_bucket)  # todo: list_objects_v2 pagination (1k items max/ page)
    print(list_objects)
    for obj in list_objects['Contents']:
        if not obj['Key'].startswith(name):
            continue

        obj_class = obj['StorageClass']
        if obj_class in ARCHIVE_CLASSES:
            try:
                s3.restore_object(Bucket=source_bucket, Key=obj['Key'], RestoreRequest={'Days': 1})
                dynamodb.put_item(TableName='MPCS-Practicum-2024',
                                  Item={'action_id': {'S': action_id}, 'object_id': {'S': obj['Key']}})
                # set_sns_topic(obj['Key'], action_id)
            except Exception as e:
                print(e)
                return False  # todo: error handling

    return True


def set_sns_topic(obj_key, action_id):
    sns = boto3.client('sns')
    response = sns.create_topic(
        Name='string',
        Attributes={
            'string': 'string'
        },
        Tags=[
            {
                'Key': 'string',
                'Value': 'string'
            },
        ],
        DataProtectionPolicy='string'
    )


if __name__ == "__main__":
    print(thaw_objects('mpcs-practicum/testdata', '1'))
