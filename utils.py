import boto3


def get_objects(bucket_name):
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name)

    return response


def thaw_objects(complete_path, action_id):
    s3 = boto3.client('s3')
    dynamodb = boto3.client('dynamodb')
    source_bucket = complete_path.split('/')[0]
    prefix = '/'.join(complete_path.split('/')[1:])
    print(source_bucket)
    response = s3.list_objects_v2(Bucket=source_bucket)
    for obj in response['Contents']:
        obj_class = s3.get_object_storage_class(Bucket=source_bucket, Key=obj['Key'])
        if obj_class == 'GLACIER' or obj_class == 'DEEP_ARCHIVE' or obj_class == 'INTELLIGENT_TIERING':
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
