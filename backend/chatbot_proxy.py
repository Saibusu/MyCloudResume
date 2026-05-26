import json
import boto3

lex = boto3.client("lexv2-runtime", region_name="us-east-1")

BOT_ID       = "F7MS13BUCP"
BOT_ALIAS_ID = "TSTALIASID"
LOCALE_ID    = "en_US"

def lambda_handler(event, context):
    if (event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS"
            or event.get("httpMethod") == "OPTIONS"):
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "https://saibusu.com",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }

    body = json.loads(event.get("body") or "{}")
    user_message = body.get("message", "")
    session_id   = body.get("session_id", "default-user")

    try:
        response = lex.recognize_text(
            botId=BOT_ID,
            botAliasId=BOT_ALIAS_ID,
            localeId=LOCALE_ID,
            sessionId=session_id,
            text=user_message
        )
        messages = response.get("messages", [])
        reply = messages[0]["content"] if messages else "Sorry, I didn't understand. Try: 'how many visitors' or 'who are you'"
    except Exception as e:
        print(f"LEX_ERROR: {e}")
        reply = "Chatbot is temporarily unavailable, please try again later."

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://saibusu.com",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps({"reply": reply}, ensure_ascii=False)
    }
