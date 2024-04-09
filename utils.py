import boto3


def get_objects(bucket_name):
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name)

    return response


# transfer objects that are of class standard storage class; thaw those that are of class deep archive storage class
def transfer_objects(source_bucket, destination_bucket):
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=source_bucket)
    for obj in response['Contents']:
        obj_class = s3.get_object_storage_class(Bucket=source_bucket, Key=obj['Key'])
        if obj_class != 'GLACIER' and obj_class != 'DEEP_ARCHIVE' and obj_class != 'INTELLIGENT_TIERING': # todo INTELLIGENT_TIERING
            try:
                s3.copy_object(Bucket=destination_bucket, CopySource={'Bucket': source_bucket, 'Key': obj['Key']},
                               Key=obj['Key'])
            except Exception as e:
                print(e)
                return False # todo
            s3.delete_object(Bucket=source_bucket, Key=obj['Key'])
        else:
            s3.restore_object(Bucket=source_bucket, Key=obj['Key'], RestoreRequest={'Days': 1})

    return True
