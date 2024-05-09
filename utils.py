import concurrent
from datetime import *

import boto3
from dateutil.tz import *

from model.ThawMetadata import ThawMetadata
from model.ThawStatus import ThawStatus

GLACIER = 'GLACIER'
DEEP_ARCHIVE = 'DEEP_ARCHIVE'
INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
ARCHIVE_CLASSES = [GLACIER, DEEP_ARCHIVE, INTELLIGENT_TIERING]


def thaw_objects(complete_path, action_id):
    s3 = boto3.client('s3')
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')  # todo: must specify region_name
    source_bucket = complete_path.split('/')[1]
    prefix = '/'.join(complete_path.split('/')[2:])
    keys = []
    print(complete_path)
    print(source_bucket)
    print(prefix)

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(
        Bucket=source_bucket,
        Prefix=prefix,
        OptionalObjectAttributes=
        [
            'RestoreStatus',
        ]
    )

    possibly_completed_objects_key = []
    for page in pages:
        for obj in page['Contents']:
            if obj['StorageClass'] in ARCHIVE_CLASSES:
                keys.append(obj['Key'])
                status = ThawStatus.INITIATED
                if is_thaw_in_progress_or_completed(obj):
                    possibly_completed_objects_key.append(obj['Key'])

                metadata = ThawMetadata(action_id,
                                        source_bucket + "/" + obj['Key'],
                                        status,
                                        datetime.now().isoformat(),
                                        None)

                put_thaw_metadata(metadata, dynamodb)

    set_s3_notification(source_bucket, keys, s3)
    init_s3_restore(source_bucket, keys, s3)
    check_and_mark_possibly_completed_objects(action_id, source_bucket, possibly_completed_objects_key, s3, dynamodb)

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
    for k in keys:
        filter_rules = [{
            'Name': 'prefix',
            'Value': k,
        }]

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


def check_and_mark_possibly_completed_objects(action_id: str, bucket_name: str, keys: [str], s3_client: boto3.client,
                                              dynamodb_client: boto3.client):
    def parse_string(input_string):
        import re
        pattern = r'ongoing-request="(\w+)"(?:,\s+expiry-date="(.+?)")?'
        matches = re.search(pattern, input_string)
        if matches:
            ongoing_request = matches.group(1)
            expiry_datetime = matches.group(2) if matches.group(2) else None
            return ongoing_request, expiry_datetime
        else:
            return None, None

    for key in keys:
        response = s3_client.head_object(Bucket=bucket_name, Key=key)
        if response['Restore']:
            ongoing_request, expiry_datetime = parse_string(response['Restore'])
            expiry_datetime = datetime.strptime(expiry_datetime, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
            if ongoing_request == 'false':
                metadata = ThawMetadata(action_id,
                                        bucket_name + "/" + key,
                                        ThawStatus.COMPLETED,
                                        None,
                                        expiry_datetime)
                put_thaw_metadata(metadata, dynamodb_client)


def put_thaw_metadata(metadata: ThawMetadata, dynamodb_client: boto3.client):
    dynamodb_client.put_item(TableName='MPCS-Practicum-2024', Item=metadata.marshal())  # todo: table name


def is_thaw_in_progress_or_completed(obj):
    return 'RestoreStatus' in obj and ((obj['RestoreStatus']['IsRestoreInProgress']) or
                                       (not obj['RestoreStatus']['IsRestoreInProgress'] and
                                        datetime.now(tzlocal()) < obj['RestoreStatus']['RestoreExpiryDate']))


if __name__ == "__main__":
    res = thaw_objects('/mpcs-practicum/testdata', '1')
    print(res)
