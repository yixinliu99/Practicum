import boto3

GLACIER = 'GLACIER'
DEEP_ARCHIVE = 'DEEP_ARCHIVE'
INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
ARCHIVE_CLASSES = [GLACIER, DEEP_ARCHIVE, INTELLIGENT_TIERING]

def get_objects(bucket_name):
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name)

    return response


def thaw_objects(complete_path, action_id):
    s3 = boto3.client('s3')
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    source_bucket = complete_path.split('/')[0]
    name = '/'.join(complete_path.split('/')[1:])
    print(complete_path)
    print(source_bucket)
    print(name)
    response = s3.list_objects_v2(Bucket=source_bucket) # todo: pagination (1k items)
    print(response)
    for obj in response['Contents']:
        if not obj['Key'].startswith(name):
            continue

        obj_class = obj['StorageClass']
        if obj_class in ARCHIVE_CLASSES:
            try:
                s3.restore_object(Bucket=source_bucket, Key=obj['Key'], RestoreRequest={'Days': 1})
                dynamodb.put_item(TableName='MPCS-Practicum-2024',
                                  Item={'action_id': {'S': action_id}, 'object_id': {'S': obj['Key']}})
            except Exception as e:
                print(e)
                return False  # todo

    return True


def set_bucket_object_thawed_notification(bucket_name, lambda_arn):
    s3 = boto3.client('s3')
    s3.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration={
            'LambdaFunctionConfigurations': [
                {
                    'LambdaFunctionArn': lambda_arn,
                    'Events': [
                        's3:ObjectRestore:Completed'
                    ]
                },
            ]
        }
    )

if __name__ == "__main__":
    print(thaw_objects('mpcs-practicum/testdata', '1'))
