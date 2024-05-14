import boto3

SQS_EVENT_SOURCE = "aws:sqs"
S3_EVENT_SOURCE = "aws:s3"


def get_action_ids(object_id, table):
    response = table.query(
        IndexName='object_id-index',
        Select='ALL_PROJECTED_ATTRIBUTES',
        KeyConditionExpression='object_id = :object_id',
        ExpressionAttributeValues={
            ':object_id': object_id
        }
    )
    print(response)
    return [item['action_id'] for item in response.get('Items', [])]


# Query for action_id of the objects first, then update the status and expiry_time of the objects in the DynamoDB table
def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table_name = 'MPCS-Practicum-2024'
    table = dynamodb.Table(table_name)

    try:
        for record in event["Records"]:
            if record.get("eventSource") == S3_EVENT_SOURCE:
                object_key = record['s3']['object']['key']
                bucket_name = record['s3']['bucket']['name']
                object_id = bucket_name + '/' + object_key
                expiry_time = record['glacierEventData']['restoreEventData']['lifecycleRestorationExpiryTime']
                print(object_id)

                action_ids = get_action_ids(object_id, table)
                for action_id in action_ids:
                    update_expression = "SET #attr_name1 = :attr_value1, #attr_name2 = :attr_value2"
                    expression_attribute_names = {'#attr_name1': 'thaw_status', '#attr_name2': 'expiry_time'}
                    expression_attribute_values = {':attr_value1': 'COMPLETED', ':attr_value2': expiry_time}

                    table.update_item(
                        Key={
                            'object_id': object_id,
                            'action_id': action_id
                        },
                        UpdateExpression=update_expression,
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values
                    )

        return {
            'statusCode': 200,
            'body': 'Item successfully added to DynamoDB table'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
