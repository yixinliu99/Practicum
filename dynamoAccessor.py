import boto3
from typing import Any, Dict, Optional


class DynamoAccessor:
    def __init__(self, client: boto3.client, table_name):
        self.client = client
        self.table_name = table_name

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = self.client.get_item(TableName=self.table_name, Key=key)
        return response.get('Item')
