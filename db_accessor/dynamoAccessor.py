from datetime import datetime, timedelta
import boto3
from typing import Any, Dict, Optional


class DynamoAccessor:
    def __init__(self, client: boto3.client, table_name):
        self.client = client
        self.table_name = table_name

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = self.client.get_item(TableName=self.table_name, Key=key)
        return response.get('Item')

    def put_item(self, item: Dict[str, Any], overwrite: bool = False):
        item = self._add_expiration(item)
        if overwrite:
            self.client.put_item(TableName=self.table_name, Item=item)
        else:
            self.client.put_item(TableName=self.table_name, Item=item, ConditionExpression='attribute_not_exists(pk)')

    def update_item(self, key: Dict[str, Any], update_expression: str, expression_attribute_values: Dict[str, Any],
                    expression_attribute_names: Dict[str, Any] = None):
        self.client.update_item(
            TableName=self.table_name,
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

    def query_items(self, partition_key_expression: str, sort_key_expression: str, key_mapping: Dict[str, Any],
                    index_name: str, select: str):
        key_condition_expression = f"{partition_key_expression}"
        if sort_key_expression:
            key_condition_expression += f" AND {sort_key_expression}"
        response = self.client.query(
            TableName=self.table_name,
            IndexName=index_name,
            Select=select,
            KeyConditionExpression=key_condition_expression,
            ExpressionAttributeValues=key_mapping
        )

        return response

    def delete_items(self, keys: list[Dict[str, Any]]):
        for key in keys:
            self.client.delete_item(TableName=self.table_name, Key=key)

    @staticmethod
    def _add_expiration(item: Dict[str, Any]) -> Dict[str, Any]:
        expiration_time = int((datetime.now() + timedelta(days=90)).timestamp())
        item['item_expiration_time'] = {'N': str(expiration_time)}

        return item
