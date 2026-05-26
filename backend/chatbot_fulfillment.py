import json
import urllib.request

VISITOR_API_URL = "https://3ai7u70ypd.execute-api.us-east-1.amazonaws.com/prod/visitor"

def lambda_handler(event, context):
    intent_name = event["sessionState"]["intent"]["name"]

    if intent_name == "GetVisitorCount":
        return handle_visitor_count(event)
    elif intent_name == "AskAboutMe":
        return close(event, "I am Lee Hsuan-Chieh, a Computer Science student at Tatung University, focused on cloud architecture and information security. GitHub: github.com/Saibusu")
    else:
        return close(event, "Sorry, I didn't understand. You can ask: How many visitors? or Who are you?")

def handle_visitor_count(event):
    try:
        req = urllib.request.Request(
            VISITOR_API_URL,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            count = data.get("count", "unknown")
        message = f"This website has been visited {count} times!"
    except Exception:
        message = "Visitor count is temporarily unavailable, please try again later."
    return close(event, message)

def close(event, message):
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                "name": event["sessionState"]["intent"]["name"],
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message
            }
        ]
    }
