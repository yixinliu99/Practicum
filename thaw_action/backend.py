import concurrent
import json
import os
from datetime import *
import boto3, botocore
from dateutil.tz import *
from thaw_action.model.ThawMetadata import ThawMetadata
from thaw_action.model.ThawStatus import ThawStatus
from db_accessor import dynamoAccessor
from thaw_action.utils import retry
from thaw_action.utils import MaximumRetryLimitExceeded
from flask import current_app


def thaw_objects(complete_path, action_status):
    complete_path = complete_path[0]
    action_id = action_status['action_id']
    s3 = boto3.client('s3')
    datatypes = current_app.datatypes
    dynamodb = boto3.client('dynamodb', region_name=datatypes.REGION_NAME)
    source_bucket = complete_path.split('/')[1]
    prefix = '/'.join(complete_path.split('/')[2:])
    keys = []
    objects_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.OBJECTS_STATUS_TABLE_NAME)
    action_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.ACTION_STATUS_TABLE_NAME)
    action_status_accessor.put_item(item={
        datatypes.ACTION_ID: {'S': action_id},
        'contents': {'S': json.dumps(action_status)}
    })

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
            if obj['StorageClass'] in datatypes.ARCHIVE_CLASSES:
                keys.append(obj['Key'])
                status = ThawStatus.INITIATED
                if _is_thaw_in_progress_or_completed(obj):
                    possibly_completed_objects_key.append(obj['Key'])

                metadata = ThawMetadata(action_id,
                                        source_bucket + "/" + obj['Key'],
                                        status,
                                        datetime.now().isoformat(),
                                        None)

                objects_status_accessor.put_item(metadata.marshal())

    _set_s3_notification(source_bucket, keys, s3)
    _init_s3_restore(source_bucket, keys, s3)
    _check_and_mark_possibly_completed_objects(action_id, source_bucket, possibly_completed_objects_key, s3,
                                               objects_status_accessor)

    return True


def check_thaw_status(action_id: str) -> tuple[dict, bool | None]:
    datatypes = current_app.datatypes
    objects_status_accessor = dynamoAccessor.DynamoAccessor(boto3.client('dynamodb', region_name=datatypes.REGION_NAME),
                                                            datatypes.OBJECTS_STATUS_TABLE_NAME)
    action_status = get_thaw_status(action_id)
    if not action_status:
        return action_status, None

    result = objects_status_accessor.query_items(
        partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
        sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
        key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                     f":{datatypes.THAW_STATUS}": {"S": ThawStatus.INITIATED}},
        index_name=datatypes.GSI_INDEX_NAME,
        select="COUNT"
    )
    if result['Count'] == 0:
        return action_status, True
    else:
        return action_status, False


def get_thaw_status(action_id: str) -> dict:
    datatypes = current_app.datatypes
    action_status_accessor = dynamoAccessor.DynamoAccessor(boto3.client('dynamodb', region_name=datatypes.REGION_NAME),
                                                           datatypes.ACTION_STATUS_TABLE_NAME)
    action_status = action_status_accessor.get_item(key={datatypes.ACTION_ID: {"S": action_id}})

    return json.loads(action_status['contents']['S']) if action_status else None


def update_thaw_status(action_id: str, thaw_status: str) -> bool:
    datatypes = current_app.datatypes
    dynamodb = boto3.client('dynamodb', region_name=datatypes.REGION_NAME)
    action_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.ACTION_STATUS_TABLE_NAME)
    action_status_accessor.update_item(
        key={
            'action_id': {"S": action_id},
        },
        update_expression="SET #attr_name = :attr_value",
        expression_attribute_values={':attr_value': {"S": thaw_status}},
        expression_attribute_names={'#attr_name': 'status'}
    )

    return True


def cleanup(action_id: str):
    datatypes = current_app.datatypes
    dynamodb = boto3.client('dynamodb', region_name=datatypes.REGION_NAME)
    objects_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.OBJECTS_STATUS_TABLE_NAME)
    action_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.ACTION_STATUS_TABLE_NAME)
    initiated_objects = objects_status_accessor.query_items(
        partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
        sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
        key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                     f":{datatypes.THAW_STATUS}": {"S": ThawStatus.INITIATED}},
        index_name=datatypes.GSI_INDEX_NAME,
        select="ALL_PROJECTED_ATTRIBUTES"
    )
    completed_objects = objects_status_accessor.query_items(
        partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
        sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
        key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                     f":{datatypes.THAW_STATUS}": {"S": ThawStatus.COMPLETED}},
        index_name=datatypes.GSI_INDEX_NAME,
        select="ALL_PROJECTED_ATTRIBUTES"
    )
    object_ids = []
    for obj in initiated_objects['Items']:
        object_ids.append(obj['object_id']['S'])
    for obj in completed_objects['Items']:
        object_ids.append(obj['object_id']['S'])

    keys = [
        {
            datatypes.ACTION_ID: {"S": action_id},
            datatypes.OBJECT_ID: {"S": object_id}
        }
        for object_id in object_ids
    ]

    action_status_accessor.delete_items(keys=[{datatypes.ACTION_ID: {"S": action_id}}])
    objects_status_accessor.delete_items(keys=keys)


def _initiate_restore(s3_client: boto3.client, bucket_name: str, key: str, days: int):
    try:
        s3_client.restore_object(
            Bucket=bucket_name,
            Key=key,
            RestoreRequest={'Days': days})
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'RestoreAlreadyInProgress':
            pass


def _init_s3_restore(source_bucket: str, keys: list, s3_client: boto3.client):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(
            _initiate_restore,
            s3_client=s3_client,
            bucket_name=source_bucket,
            key=key,
            days=1)  # todo: lifecycle policy
            for key in keys]
        for future in concurrent.futures.as_completed(futures):
            future.result()


@retry(times=3, exceptions=MaximumRetryLimitExceeded)
def _set_s3_notification(bucket_name: str, keys: [str], s3_client: boto3.client):
    common_prefix = os.path.commonprefix(keys)
    datatypes = current_app.datatypes
    filter_rules = [{
        'Name': 'prefix',
        'Value': common_prefix,
    }]
    notification_configuration = {
        'TopicConfigurations': [
            {
                'TopicArn': datatypes.SNS_TOPIC_ARN,
                'Events': [
                    's3:ObjectRestore:Completed'
                ],
                'Filter': {
                    "Key": {
                        'FilterRules': filter_rules
                    }
                }
            }
        ]
    }
    s3_client.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration=notification_configuration
    )


def _check_and_mark_possibly_completed_objects(action_id: str, bucket_name: str, keys: [str], s3_client: boto3.client,
                                               dynamo_accessor: dynamoAccessor.DynamoAccessor):
    def parse_string(input_string):
        import re
        pattern = r'ongoing-request="(\w+)"(?:,\s+expiry-date="(.+?)")?'
        matches = re.search(pattern, input_string)
        if matches:
            return matches.group(1), matches.group(2) if matches.group(2) else None
        else:
            return None, None

    datatypes = current_app.datatypes
    for key in keys:
        response = s3_client.head_object(Bucket=bucket_name, Key=key)
        if response['Restore']:
            ongoing_request, expiry_datetime = parse_string(response['Restore'])
            object_id = bucket_name + "/" + key
            if ongoing_request == 'false':
                expiry_time = datetime.strptime(expiry_datetime, "%a, %d %b %Y %H:%M:%S %Z").isoformat()
                update_expression = "SET #attr_name1 = :attr_value1, #attr_name2 = :attr_value2"
                expression_attribute_names = {'#attr_name1': datatypes.THAW_STATUS,
                                              '#attr_name2': datatypes.EXPIRY_TIME}
                expression_attribute_values = {':attr_value1': {"S": ThawStatus.COMPLETED},
                                               ':attr_value2': {"S": expiry_time}}
                dynamo_accessor.update_item(
                    key={
                        datatypes.ACTION_ID: {"S": action_id},
                        datatypes.OBJECT_ID: {"S": object_id},
                    },
                    update_expression=update_expression,
                    expression_attribute_values=expression_attribute_values,
                    expression_attribute_names=expression_attribute_names
                )


def _is_thaw_in_progress_or_completed(obj):
    return 'RestoreStatus' in obj and ((obj['RestoreStatus']['IsRestoreInProgress']) or
                                       (not obj['RestoreStatus']['IsRestoreInProgress'] and
                                        datetime.now(tzlocal()) < obj['RestoreStatus']['RestoreExpiryDate']))


if __name__ == '__main__':
    dummy_action_status = {'action_id': 'UWt6fUdVZLZ5', 'completion_time': None,
                           'creator_id': 'urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d', 'details': {},
                           'display_status': 'ACTIVE', 'label': None,
                           'manage_by': ['urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d'],
                           'monitor_by': ['urn:globus:auth:identity:cbfba6c9-1a8f-4d42-9041-c73fa6e7d87d'],
                           'release_after': 'P30D',
                           'start_time': '2024-05-13T19:42:06.795219+00:00', 'status': 'ACTIVE'}
    dummy_action_status = json.loads(json.dumps(dummy_action_status))
    res = thaw_objects(['/mpcs-practicum/test00'], dummy_action_status)
    print(res)
    js, res = check_thaw_status('UWt6fUdVZLZ5')
    print(js, res)
