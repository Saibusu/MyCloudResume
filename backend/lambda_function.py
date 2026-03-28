import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ResumeVisitorCount')

def lambda_handler(event, context):
    """
    訪客計數器 Lambda：
    1. 接收來自 API Gateway 的請求
    2. 使用 DynamoDB 原子操作 (Atomic Counter) 更新計數
    3. 回傳包含 CORS Header 的 JSON 回應
    """
    try:
        response = table.update_item(
            Key={'id': 'total_visits'},
            UpdateExpression='ADD #c :val',
            ExpressionAttributeNames={'#c': 'count'},
            ExpressionAttributeValues={':val': 1},
            ReturnValues="UPDATED_NEW"
        )

        current_count = str(response['Attributes']['count'])

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://saibusu.com',
                'Access-Control-Allow-Methods': 'OPTIONS,GET'
            },
            'body': json.dumps({
                'message': f'Lambda 接通成功！軒杰，你是第 {current_count} 位訪客。',
                'count': current_count,
                'status': 'success'
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal Server Error'})
        }
