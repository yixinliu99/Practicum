import concurrent
from datetime import *

import boto3
from dateutil.tz import *

from model.ThawMetadata import ThawMetadata
from model.ThawStatus import ThawStatus
from db_accessor import dynamoAccessor

GLACIER = 'GLACIER'
DEEP_ARCHIVE = 'DEEP_ARCHIVE'
INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
ARCHIVE_CLASSES = [GLACIER, DEEP_ARCHIVE, INTELLIGENT_TIERING]
TABLE_NAME = 'MPCS-Practicum-2024'
REGION_NAME = 'us-east-1'
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:074950442422:Practicum-2024'
GSI_INDEX_NAME = 'action_id-thaw_status-index'


def thaw_objects(complete_path, action_id):
    s3 = boto3.client('s3')
    dynamodb = boto3.client('dynamodb', region_name=REGION_NAME)
    source_bucket = complete_path.split('/')[1]
    prefix = '/'.join(complete_path.split('/')[2:])
    keys = []
    dynamo_accessor = dynamoAccessor.DynamoAccessor(dynamodb, TABLE_NAME)
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

                dynamo_accessor.put_item(metadata.marshal())

    set_s3_notification(source_bucket, keys, s3)
    init_s3_restore(source_bucket, keys, s3)
    check_and_mark_possibly_completed_objects(action_id, source_bucket, possibly_completed_objects_key, s3,
                                              dynamo_accessor)

    return True


def init_s3_restore(source_bucket: str, keys: list, s3_client: boto3.client):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(
            s3_client.restore_object,
            Bucket=source_bucket,
            Key=key,
            RestoreRequest={'Days': 1})  # todo: lifecycle policy
            for key in keys]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def set_s3_notification(bucket_name: str, keys: [str], s3_client: boto3.client):
    def set_notification(key):
        filter_rules = [{
            'Name': 'prefix',
            'Value': key,
        }]

        notification_configuration = {
            'TopicConfigurations': [
                {
                    'TopicArn': SNS_TOPIC_ARN,
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(set_notification, key) for key in keys]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def check_and_mark_possibly_completed_objects(action_id: str, bucket_name: str, keys: [str], s3_client: boto3.client,
                                              dynamo_accessor: dynamoAccessor.DynamoAccessor):
    def parse_string(input_string):
        import re
        pattern = r'ongoing-request="(\w+)"(?:,\s+expiry-date="(.+?)")?'
        matches = re.search(pattern, input_string)
        if matches:
            return matches.group(1), matches.group(2) if matches.group(2) else None
        else:
            return None, None

    for key in keys:
        response = s3_client.head_object(Bucket=bucket_name, Key=key)
        if response['Restore']:
            ongoing_request, expiry_datetime = parse_string(response['Restore'])
            expiry_time = datetime.strptime(expiry_datetime, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
            object_id = bucket_name + "/" + key
            if ongoing_request == 'false':
                update_expression = "SET #attr_name1 = :attr_value1, #attr_name2 = :attr_value2"
                expression_attribute_names = {'#attr_name1': ThawMetadata.THAW_STATUS,
                                              '#attr_name2': ThawMetadata.EXPIRY_TIME}
                expression_attribute_values = {':attr_value1': {"S": ThawStatus.COMPLETED},
                                               ':attr_value2': {"S": expiry_time}}
                dynamo_accessor.update_item(
                    key={
                        'object_id': {"S": object_id},
                    },
                    update_expression=update_expression,
                    expression_attribute_values=expression_attribute_values,
                    expression_attribute_names=expression_attribute_names
                )


def is_thaw_in_progress_or_completed(obj):
    return 'RestoreStatus' in obj and ((obj['RestoreStatus']['IsRestoreInProgress']) or
                                       (not obj['RestoreStatus']['IsRestoreInProgress'] and
                                        datetime.now(tzlocal()) < obj['RestoreStatus']['RestoreExpiryDate']))


def check_thaw_status(action_id: str):
    dynamo_accessor = dynamoAccessor.DynamoAccessor(boto3.client('dynamodb', region_name=REGION_NAME), TABLE_NAME)
    result = dynamo_accessor.query_items(
        partition_key_expression=f"{ThawMetadata.ACTION_ID} = :{ThawMetadata.ACTION_ID}",
        sort_key_expression=f"{ThawMetadata.THAW_STATUS} = :{ThawMetadata.THAW_STATUS}",
        key_mapping={f":{ThawMetadata.ACTION_ID}": {"S": action_id},
                     f":{ThawMetadata.THAW_STATUS}": {"S": ThawStatus.INITIATED}},
        index_name=GSI_INDEX_NAME,
        select="COUNT"
    )

    return result['Count'] == 0


if __name__ == "__main__":
    # res = thaw_objects('/mpcs-practicum/testdata', '1')
    res = check_thaw_status('1')
    print(res)
