import boto3

SQS_EVENT_SOURCE = "aws:sqs"
S3_EVENT_SOURCE = "aws:s3"


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

                update_expression = "SET #attr_name1 = :attr_value1, #attr_name2 = :attr_value2"
                expression_attribute_names = {'#attr_name1': 'status', '#attr_name2': 'expiry_time'}
                expression_attribute_values = {':attr_value1': 'COMPLETED', ':attr_value2': expiry_time}

                table.update_item(
                    Key={
                        'object_id': object_id
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
