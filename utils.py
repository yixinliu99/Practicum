import concurrent
import boto3
from model.ThawMetadata import ThawMetadata
from model.ThawStatus import ThawStatus
from datetime import *
from dateutil.tz import *

GLACIER = 'GLACIER'
DEEP_ARCHIVE = 'DEEP_ARCHIVE'
INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
ARCHIVE_CLASSES = [GLACIER, DEEP_ARCHIVE, INTELLIGENT_TIERING]


def thaw_objects(complete_path, action_id):
    s3 = boto3.client('s3')
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')  # todo: must specify region_name
    source_bucket = complete_path.split('/')[0]
    name = '/'.join(complete_path.split('/')[1:])
    keys = []
    print(complete_path)
    print(source_bucket)
    print(name)

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(
        Bucket=source_bucket,
        Prefix=name,
        OptionalObjectAttributes=
        [
            'RestoreStatus',
        ]
    )

    for page in pages:
        for obj in page['Contents']:
            if obj['StorageClass'] in ARCHIVE_CLASSES:
                keys.append(obj['Key'])
                status = ThawStatus.INITIATED
                if 'RestoreStatus' in obj and not obj['RestoreStatus']['IsRestoreInProgress'] and datetime.now(tzlocal()) < obj['RestoreStatus']['RestoreExpiryDate']:
                    status = ThawStatus.COMPLETED

                metadata = ThawMetadata(action_id,
                                        source_bucket + "/" + obj['Key'],
                                        status,
                                        datetime.now().isoformat(),
                                        None,
                                        None)

                put_thaw_metadata(metadata, dynamodb)

    set_s3_notification(source_bucket, keys, s3)
    init_s3_restore(source_bucket, keys, s3)

    return True


def init_s3_restore(source_bucket: str, keys: list, s3_client: boto3.client):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(
            s3_client.restore_object,
            Bucket=source_bucket,
            Key=key,
            RestoreRequest={'Days': 1})
            for key in keys]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(e)  # todo: logger
                return False


def set_s3_notification(bucket_name: str, keys: [str], s3_client: boto3.client):
    filter_rules = []
    for k in keys:
        filter_rules.append({
            'Name': 'prefix',
            'Value': k,
        })

    notification_configuration = {
        'TopicConfigurations': [
            {
                'TopicArn': 'arn:aws:sns:us-east-1:074950442422:Practicum-2024',  # todo: SNS ARN
                'Events': [
                    's3:ObjectRestore:*'
                ],
                'Filter': {
                    "Key": {
                        'FilterRules': filter_rules
                    }
                }
            }
        ]
    }
    try:
        response = s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_configuration
        )
        print(response)

    except Exception as e:
        print(e)


def put_thaw_metadata(metadata: ThawMetadata, dynamodb_client: boto3.client):
    dynamodb_client.put_item(TableName='MPCS-Practicum-2024', Item=metadata.marshal())  # todo: table name


if __name__ == "__main__":
    res = thaw_objects('mpcs-practicum/test00', '1')
    print(res)
