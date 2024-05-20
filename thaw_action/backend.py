import concurrent
import json
from datetime import *
import boto3, botocore
from dateutil.tz import *
from thaw_action.model.ThawMetadata import ThawMetadata
from thaw_action.model.ThawStatus import ThawStatus
from db_accessor import dynamoAccessor
from thaw_action.utils import retry, get_data_types, MaximumRetryLimitExceeded


def thaw_objects(complete_path, action_status):
    complete_path = complete_path[0]
    action_id = action_status['action_id']
    s3 = boto3.client('s3')
    datatypes = get_data_types()
    dynamodb = boto3.client('dynamodb', region_name=datatypes.REGION_NAME)
    source_bucket = complete_path.split('/')[1]
    glacier_obj_keys = []
    objects_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.OBJECTS_STATUS_TABLE_NAME)
    action_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.ACTION_STATUS_TABLE_NAME)
    prefix = '/'.join(complete_path.split('/')[2:])
    glacier_obj_keys, possibly_completed_objects_key = _get_s3_objects_and_mark_status(action_id, source_bucket,
                                                                                       glacier_obj_keys, prefix,
                                                                                       s3)

    action_status_accessor.put_item(item={
        datatypes.ACTION_ID: {'S': action_id},
        'contents': {'S': json.dumps(action_status)},
        'bucket_name': {'S': source_bucket},
        'next_query_time': {'S': (datetime.now() + timedelta(hours=12)).isoformat()}
    })

    _set_s3_notification(source_bucket, s3)
    _init_s3_restore(source_bucket, glacier_obj_keys, s3)
    _check_and_mark_possibly_completed_objects(action_id, source_bucket, possibly_completed_objects_key, s3,
                                               objects_status_accessor)

    return True


def check_thaw_status(action_id: str) -> tuple[dict, bool | None]:
    datatypes = get_data_types()
    objects_status_accessor = dynamoAccessor.DynamoAccessor(boto3.client('dynamodb', region_name=datatypes.REGION_NAME),
                                                            datatypes.OBJECTS_STATUS_TABLE_NAME)
    action_status = get_action_status(action_id)
    if not action_status:
        return action_status, None
    next_query_time = datetime.fromisoformat(action_status['next_query_time']['S'])
    action_status = json.loads(action_status['contents']['S'])

    result = objects_status_accessor.query_items(
        partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
        sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
        key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                     f":{datatypes.THAW_STATUS}": {"S": ThawStatus.INITIATED}},
        index_name=datatypes.ACTION_STATUS_GSI_INDEX_NAME,
        select="COUNT"
    )
    if result['Count'] == 0:
        return action_status, True
    else:
        if datetime.now() > next_query_time:
            # update next_query_time
            next_query_time = (datetime.now() + timedelta(hours=int(datatypes.S3_QUERY_INTERVAL))).isoformat()
            action_status_accessor = dynamoAccessor.DynamoAccessor(
                boto3.client('dynamodb', region_name=datatypes.REGION_NAME),
                datatypes.ACTION_STATUS_TABLE_NAME)
            action_status_accessor.update_item(
                key={
                    'action_id': {"S": action_id},
                },
                update_expression="SET #attr_name = :attr_value",
                expression_attribute_values={':attr_value': {"S": next_query_time}},
                expression_attribute_names={'#attr_name': 'next_query_time'}
            )

            # restart thaw for uncompleted objects
            uncompleted_objects = objects_status_accessor.query_items(
                partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
                sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
                key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                             f":{datatypes.THAW_STATUS}": {"S": ThawStatus.INITIATED}},
                index_name=datatypes.ACTION_STATUS_GSI_INDEX_NAME,
                select="ALL_PROJECTED_ATTRIBUTES"
            )
            if not uncompleted_objects['Items']:
                return action_status, True

            source_bucket = '/' + uncompleted_objects['Items'][0]['object_id']['S'].split('/')[0]
            thaw_objects([source_bucket], action_status)

        return action_status, False


def get_action_status(action_id: str) -> dict:
    datatypes = get_data_types()
    action_status_accessor = dynamoAccessor.DynamoAccessor(boto3.client('dynamodb', region_name=datatypes.REGION_NAME),
                                                           datatypes.ACTION_STATUS_TABLE_NAME)
    action_status = action_status_accessor.get_item(key={datatypes.ACTION_ID: {"S": action_id}})

    return action_status if action_status else None


def update_action_status(action_id: str, action_status: str) -> bool:
    datatypes = get_data_types()
    dynamodb = boto3.client('dynamodb', region_name=datatypes.REGION_NAME)
    action_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.ACTION_STATUS_TABLE_NAME)
    action_status_accessor.update_item(
        key={
            'action_id': {"S": action_id},
        },
        update_expression="SET #attr_name = :attr_value",
        expression_attribute_values={':attr_value': {"S": action_status}},
        expression_attribute_names={'#attr_name': 'contents'}
    )

    return True


def cleanup(action_id: str):
    datatypes = get_data_types()
    dynamodb = boto3.client('dynamodb', region_name=datatypes.REGION_NAME)
    objects_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.OBJECTS_STATUS_TABLE_NAME)
    action_status_accessor = dynamoAccessor.DynamoAccessor(dynamodb, datatypes.ACTION_STATUS_TABLE_NAME)
    initiated_objects = objects_status_accessor.query_items(
        partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
        sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
        key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                     f":{datatypes.THAW_STATUS}": {"S": ThawStatus.INITIATED}},
        index_name=datatypes.ACTION_STATUS_GSI_INDEX_NAME,
        select="ALL_PROJECTED_ATTRIBUTES"
    )
    completed_objects = objects_status_accessor.query_items(
        partition_key_expression=f"{datatypes.ACTION_ID} = :{datatypes.ACTION_ID}",
        sort_key_expression=f"{datatypes.THAW_STATUS} = :{datatypes.THAW_STATUS}",
        key_mapping={f":{datatypes.ACTION_ID}": {"S": action_id},
                     f":{datatypes.THAW_STATUS}": {"S": ThawStatus.COMPLETED}},
        index_name=datatypes.ACTION_STATUS_GSI_INDEX_NAME,
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
            days=30)
            for key in keys]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def _get_s3_objects_and_mark_status(action_id: str, source_bucket: str, glacier_obj_keys: [str], prefix: str,
                                    s3: boto3.client) -> tuple[list, list]:
    datatypes = get_data_types()
    paginator = s3.get_paginator('list_objects_v2')
    objects_status_accessor = dynamoAccessor.DynamoAccessor(boto3.client('dynamodb', region_name=datatypes.REGION_NAME),
                                                            datatypes.OBJECTS_STATUS_TABLE_NAME)
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
                glacier_obj_keys.append(obj['Key'])
                status = ThawStatus.INITIATED
                if _is_thaw_in_progress_or_completed(obj):
                    possibly_completed_objects_key.append(obj['Key'])

                metadata = ThawMetadata(action_id,
                                        source_bucket + "/" + obj['Key'],
                                        status,
                                        datetime.now().isoformat(),
                                        None)

                objects_status_accessor.put_item(metadata.marshal())

    return glacier_obj_keys, possibly_completed_objects_key


def _create_s3_notification_policy(SNSArn: str, Events: list):
    policy = {
        'TopicArn': SNSArn,
        'Events': Events,
    }
    return policy


@retry(times=3, exceptions=MaximumRetryLimitExceeded)
def _set_s3_notification(bucket_name: str, s3_client: boto3.client):
    datatypes = get_data_types()
    events = ['s3:ObjectRestore:Completed']
    absent_events = []
    config_list, configuration = _get_s3_notification_config(bucket_name, s3_client)

    if len(config_list) == 0:
        policy = _create_s3_notification_policy(datatypes.SNS_TOPIC_ARN, events)
        event_dict = {'TopicConfigurations': [policy]}
        _put_s3_notification_configuration(bucket_name, s3_client, event_dict)
    else:
        for event in events:
            if event not in config_list:
                absent_events.append(event)
        if len(absent_events) != 0:
            policy = _create_s3_notification_policy(datatypes.SNS_TOPIC_ARN, events)
            event_dict = {'TopicConfigurations': [policy]}
            if 'TopicConfigurations' in configuration.keys():
                configuration['TopicConfigurations'].extend(event_dict['TopicConfigurations'])
            else:
                configuration.update(event_dict)
            _put_s3_notification_configuration(bucket_name, s3_client, configuration)


def _put_s3_notification_configuration(bucket_name: str, s3_client: boto3.client, event_dict: dict):
    s3_client.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration=event_dict
    )


def _get_s3_notification_config(bucket_name: str, s3_client: boto3.client):
    config_list = []
    configuration = s3_client.get_bucket_notification_configuration(
        Bucket=bucket_name,
    )
    if len(configuration) != 0:
        del configuration['ResponseMetadata']
        for val in configuration.values():
            if len(val) > 1:
                for v in val:
                    config_list.extend(v['Events'])
            else:
                config_list.extend(val[0]['Events'])
    return config_list, configuration


def _remove_restore_event_sub_from_s3_notification_configuration(bucket_name: str):
    s3_client = boto3.client('s3')
    config_list, configuration = _get_s3_notification_config(bucket_name, s3_client)
    if len(config_list) == 0 or 'TopicConfigurations' not in configuration.keys():
        return

    for config in configuration['TopicConfigurations']:
        if (config['TopicArn'] == get_data_types().SNS_TOPIC_ARN and
                's3:ObjectRestore:Completed' in config['Events'] and
                not _check_if_s3_bucket_restore_sub_in_use(bucket_name)):
            configuration['TopicConfigurations'].remove(config)
            _put_s3_notification_configuration(bucket_name, s3_client, configuration)


def _check_if_s3_bucket_restore_sub_in_use(bucket_name: str) -> bool:
    datatypes = get_data_types()
    action_status_accessor = dynamoAccessor.DynamoAccessor(
        boto3.client('dynamodb', region_name=get_data_types().REGION_NAME),
        get_data_types().ACTION_STATUS_TABLE_NAME)

    result = action_status_accessor.query_items(
        partition_key_expression=f"{datatypes.BUCKET_NAME} = :{datatypes.BUCKET_NAME}",
        sort_key_expression="",
        key_mapping={f":{datatypes.BUCKET_NAME}": {"S": bucket_name}},
        index_name=datatypes.BUCKET_GSI_INDEX_NAME,
        select="COUNT"
    )
    if result['Count'] == 0:
        return False
    else:
        return True


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

    datatypes = get_data_types()
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
    res = thaw_objects(['/mpcs-practicum'], dummy_action_status)
    print(res)
    js, res = check_thaw_status('UWt6fUdVZLZ5')
    print(js, res)
    _remove_restore_event_sub_from_s3_notification_configuration('mpcs-practicum-archive-2')
