import boto3
from typing import Any, Dict, Optional


class DynamoAccessor:
    def __init__(self, client: boto3.client, table_name):
        self.client = client
        self.table_name = table_name

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = self.client.get_item(TableName=self.table_name, Key=key)
        return response.get('Item')

    def put_item(self, item: Dict[str, Any]):
        self.client.put_item(TableName=self.table_name, Item=item)

    def update_item(self, key: Dict[str, Any], update_expression: str, expression_attribute_values: Dict[str, Any],
                    expression_attribute_names: Dict[str, Any] = None):
        self.client.update_item(
            TableName=self.table_name,
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
