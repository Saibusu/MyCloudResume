# 期末專案補完 ROADMAP
## 雲端履歷網站 + Amazon Lex v2 智慧訪客 Chatbot

> **目標**：在現有 S3 + Lambda + API Gateway + NeonDB 的基礎上，補上 Amazon Lex v2 Chatbot，達成期末要求。
>
> **預估時間**：3～4 小時（全部在 AWS Console 操作，不需要額外伺服器）
>
> **前置條件**：已有 AWS 帳號，且現有訪客計數器可正常運作。

---

## 現況確認

```
已完成 ✅                          待補齊 ❌
─────────────────────────────      ────────────────────────────
S3 靜態網站（saibusu.com）         Amazon Lex v2 Bot
Lambda 訪客計數（v1 Python）       Chatbot Fulfillment Lambda
Lambda 訪客計數（v2 Node.js）      API Gateway /chat 路由
API Gateway /visitor               前端 Chatbot 對話框 UI
NeonDB + Prisma ORM
GitHub Actions CI/CD
Cloudflare WAF 三層防禦
```

---

## Step 1｜建立 Amazon Lex v2 Bot（AWS Console）

**時間估計：30 分鐘**

### 1-1 進入 Lex 服務

1. 登入 AWS Console → 搜尋 **Amazon Lex** → 點進去
2. 右上角確認 Region 是 **us-east-1**（與你現有 Lambda 同區）
3. 點「**Create bot**」

### 1-2 Bot 基本設定

```
Bot name:          ResumeBot
Description:       Resume website chatbot
IAM permissions:   選「Create a role with basic Amazon Lex permissions」
COPPA:             No
Idle session TTL:  5 minutes
```

點「**Next**」

### 1-3 語言設定

```
Language:  Chinese (Traditional)   ← 選繁體中文
或
Language:  English (US)            ← 若繁中識別率差可改英文
```

點「**Done**」進入 Bot 編輯介面

---

## Step 2｜設計 Intent（意圖）

**時間估計：30 分鐘**

在左側選單點「**Intents**」，依序新增以下 3 個 Intent：

---

### Intent 1：GetVisitorCount（查詢訪客數）

點「**Add intent**」→「**Add empty intent**」→ 輸入名稱 `GetVisitorCount`

**Sample utterances（觸發語句）**，每行輸入一條後按 Enter：
```
目前有多少訪客
網站被看了幾次
訪客數量是多少
幾個人來過這個網站
現在訪客多少
how many visitors
visitor count
```

**Fulfillment**：
- 勾選「**Active**」
- Lambda function：先跳過，Step 3 建好 Lambda 後再回來填

**Closing response**（先設預設，後來由 Lambda 覆蓋）：
```
正在查詢訪客數，請稍候...
```

---

### Intent 2：AskAboutMe（詢問個人資訊）

點「**Add intent**」→ 名稱 `AskAboutMe`

**Sample utterances**：
```
你是誰
李軒杰是誰
介紹一下這個網站的主人
這個網站是誰做的
告訴我關於你的資訊
what do you do
who are you
about the owner
```

**Closing response**（直接在 Lex 設定，不需要 Lambda）：
```
我是李軒杰（LEE HSUAN-CHIEH），大同大學資訊工程學系學生，
專注於雲端架構與資訊安全。
這個履歷網站使用 AWS S3 + Lambda + API Gateway 打造，
歡迎透過 GitHub：github.com/Saibusu 聯絡我！
```

---

### Intent 3：FallbackIntent（預設已存在，直接編輯）

在左側 Intent 清單找到 **FallbackIntent** → 點進去編輯

**Closing response**：
```
抱歉我沒有聽懂，你可以問我：
• 「目前有多少訪客？」
• 「李軒杰是誰？」
```

---

### 完成後 Build Bot

右上角點「**Build**」→ 等待約 1 分鐘 → 出現「Build successful」

**測試**：點右上角「**Test**」，輸入「你是誰」確認 AskAboutMe 有觸發。

---

## Step 3｜建立 Fulfillment Lambda（chatbot-fulfillment）

**時間估計：30 分鐘**

### 3-1 建立新 Lambda 函數

1. AWS Console → **Lambda** → 「**Create function**」
2. 設定：

```
Function name:  chatbot-fulfillment
Runtime:        Python 3.12
Architecture:   arm64
```

3. 點「**Create function**」

### 3-2 貼上程式碼

在程式碼編輯器中，貼上以下程式碼（**將 YOUR_VISITOR_API_URL 換成你的真實 API 網址**）：

```python
import json
import urllib.request

# 你現有訪客計數器的 API Gateway URL（GET 用）
VISITOR_API_URL = "https://3ai7u70ypd.execute-api.us-east-1.amazonaws.com/prod/visitor"

def lambda_handler(event, context):
    intent_name = event["sessionState"]["intent"]["name"]

    if intent_name == "GetVisitorCount":
        return handle_visitor_count(event)
    elif intent_name == "AskAboutMe":
        return close(event, "李軒杰（LEE HSUAN-CHIEH），大同大學資訊工程學系，"
                     "專注雲端架構與資訊安全。GitHub：github.com/Saibusu")
    else:
        return close(event, "抱歉我沒聽懂，可以問我訪客數或網站主人資訊。")

def handle_visitor_count(event):
    try:
        # 呼叫現有訪客計數 API 取得數字（注意：這會+1，你可改為只查詢的 GET endpoint）
        req = urllib.request.Request(
            VISITOR_API_URL,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            count = data.get("count", "未知")
        message = f"目前網站共有 {count} 位訪客到訪過！"
    except Exception as e:
        message = "訪客數暫時無法取得，請稍後再試。"
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
```

4. 點「**Deploy**」儲存

### 3-3 設定 Lambda Timeout

「Configuration」→「General configuration」→「Edit」→ Timeout 改為 **10 秒** → 儲存

---

## Step 4｜將 Lambda 連接到 Lex Bot

**時間估計：15 分鐘**

### 4-1 給 Lex 權限呼叫 Lambda

1. 到 Lambda 函數頁面 → 「**Configuration**」→「**Resource-based policy**」
2. 點「**Add permissions**」：

```
Policy statement identifier:  lex-invoke
Principal:                    lexv2.amazonaws.com
Action:                       lambda:InvokeFunction
```

點「**Save**」

### 4-2 回到 Lex，設定 GetVisitorCount 的 Fulfillment

1. Lex Console → ResumeBot → Intent → **GetVisitorCount**
2. 找到「**Fulfillment**」區塊 → 「Lambda function」
3. 選擇你的 `chatbot-fulfillment` Lambda → 選版本 `$LATEST`
4. 點「**Save intent**」

### 4-3 重新 Build

右上角點「**Build**」→ 等待完成

**測試**：點「Test」→ 輸入「目前有多少訪客」→ 應該回傳實際訪客數字。

---

## Step 5｜建立 API Gateway /chat 路由

**時間估計：20 分鐘**

### 5-1 取得 Lex Bot 資訊

到 Lex Console → ResumeBot → 左側「**Bot versions**」：
- 記下 **Bot ID**（格式：`XXXXXXXXXX`）
- 記下 **Bot alias ID**（格式：`XXXXXXXXXX`，通常是 `TSTALIASID` 測試版）

### 5-2 建立 Chatbot Proxy Lambda

新建一個 Lambda 函數（或直接在現有的 chatbot-fulfillment 上加路由判斷），名稱：`chatbot-proxy`

```python
import json
import boto3

lex = boto3.client("lexv2-runtime", region_name="us-east-1")

BOT_ID      = "你的 Bot ID"        # 從 Lex Console 複製
BOT_ALIAS_ID = "TSTALIASID"        # 測試用別名
LOCALE_ID   = "zh_TW"              # 繁體中文；若用英文改 en_US

def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    user_message = body.get("message", "")
    session_id   = body.get("session_id", "default-user")

    response = lex.recognize_text(
        botId=BOT_ID,
        botAliasId=BOT_ALIAS_ID,
        localeId=LOCALE_ID,
        sessionId=session_id,
        text=user_message
    )

    messages = response.get("messages", [])
    reply = messages[0]["content"] if messages else "我不太明白，請再試一次。"

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
```

### 5-3 給 chatbot-proxy 呼叫 Lex 的 IAM 權限

Lambda → Configuration → Permissions → 點執行角色名稱 → 在 IAM Console 附加以下 Policy：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lex:RecognizeText",
      "Resource": "arn:aws:lex:us-east-1:YOUR_ACCOUNT_ID:bot-alias/YOUR_BOT_ID/TSTALIASID"
    }
  ]
}
```

### 5-4 在現有 API Gateway 加 /chat 路由

1. AWS Console → **API Gateway** → 選你現有的 HTTP API
2. 左側「**Routes**」→「**Create**」：

```
Method:  POST
Path:    /chat
```

3. 「**Integrations**」→ 將 `POST /chat` 整合到 `chatbot-proxy` Lambda
4. 點「**Deploy**」

---

## Step 6｜前端加入 Chatbot UI

**時間估計：30 分鐘**

在 `frontend/index.html` 的 `</body>` 前加入以下程式碼：

### 6-1 Chatbot 對話框 HTML

```html
<!-- Chatbot 浮動按鈕 + 對話框 -->
<div id="chat-btn" onclick="toggleChat()" title="和 ResumeBot 聊聊">💬</div>

<div id="chat-window">
  <div id="chat-header">
    <span>ResumeBot</span>
    <button onclick="toggleChat()">✕</button>
  </div>
  <div id="chat-messages">
    <div class="bot-msg">你好！我是 ResumeBot 👋<br>你可以問我：<br>• 目前有多少訪客？<br>• 李軒杰是誰？</div>
  </div>
  <div id="chat-input-row">
    <input id="chat-input" type="text" placeholder="輸入訊息..." onkeydown="if(event.key==='Enter')sendMsg()" />
    <button onclick="sendMsg()">送出</button>
  </div>
</div>
```

### 6-2 Chatbot CSS

```html
<style>
  #chat-btn {
    position: fixed;
    bottom: 70px;
    right: 24px;
    width: 52px;
    height: 52px;
    background: #2c6fad;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    z-index: 1000;
    user-select: none;
  }

  #chat-window {
    display: none;
    position: fixed;
    bottom: 130px;
    right: 24px;
    width: 320px;
    height: 420px;
    background: #1a1a2e;
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    flex-direction: column;
    z-index: 1001;
    overflow: hidden;
  }

  #chat-window.open { display: flex; }

  #chat-header {
    background: #2c6fad;
    color: #fff;
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 700;
  }

  #chat-header button {
    background: none;
    border: none;
    color: #fff;
    font-size: 16px;
    cursor: pointer;
  }

  #chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .bot-msg, .user-msg {
    max-width: 80%;
    padding: 8px 12px;
    border-radius: 12px;
    font-size: 0.88rem;
    line-height: 1.5;
    word-break: break-word;
  }

  .bot-msg {
    background: #16213e;
    color: #ccc;
    align-self: flex-start;
    border-bottom-left-radius: 2px;
  }

  .user-msg {
    background: #2c6fad;
    color: #fff;
    align-self: flex-end;
    border-bottom-right-radius: 2px;
  }

  #chat-input-row {
    display: flex;
    border-top: 1px solid #333;
  }

  #chat-input {
    flex: 1;
    background: #0f0f1a;
    border: none;
    color: #fff;
    padding: 10px 14px;
    font-size: 0.88rem;
    outline: none;
  }

  #chat-input-row button {
    background: #2c6fad;
    color: #fff;
    border: none;
    padding: 10px 16px;
    cursor: pointer;
    font-weight: 700;
    font-size: 0.88rem;
  }
</style>
```

### 6-3 Chatbot JavaScript

```html
<script>
  const CHAT_API = 'https://3ai7u70ypd.execute-api.us-east-1.amazonaws.com/prod/chat';
  // ↑ 換成你的真實 API Gateway URL + /chat

  function toggleChat() {
    document.getElementById('chat-window').classList.toggle('open');
  }

  function addMsg(text, type) {
    const box = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = type === 'user' ? 'user-msg' : 'bot-msg';
    div.innerText = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  async function sendMsg() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    addMsg(msg, 'user');
    addMsg('...', 'bot');  // loading

    try {
      const res = await fetch(CHAT_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: 'visitor-' + Date.now() })
      });
      const data = await res.json();
      // 移除 loading 訊息
      const msgs = document.getElementById('chat-messages');
      msgs.removeChild(msgs.lastChild);
      addMsg(data.reply, 'bot');
    } catch (e) {
      const msgs = document.getElementById('chat-messages');
      msgs.removeChild(msgs.lastChild);
      addMsg('連線失敗，請稍後再試。', 'bot');
    }
  }
</script>
```

---

## Step 7｜更新 infrastructure 文件

**時間估計：10 分鐘**

在 `infrastructure/` 新增 `iam-chatbot-policy.json`：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lex:RecognizeText",
      "Resource": "arn:aws:lex:us-east-1:YOUR_ACCOUNT_ID:bot-alias/YOUR_BOT_ID/TSTALIASID"
    }
  ]
}
```

---

## Step 8｜部署與測試

**時間估計：20 分鐘**

### 8-1 上傳前端到 S3

```bash
aws s3 sync ./frontend s3://saibusu.com --delete
```

或直接 `git push origin main`，GitHub Actions 會自動部署。

### 8-2 測試清單

| 測試項目 | 預期結果 |
|----------|----------|
| 開啟 saibusu.com | 右下角出現 💬 按鈕 |
| 點擊 💬 | 對話框開啟，顯示歡迎訊息 |
| 輸入「你是誰」 | Bot 回傳李軒杰個人介紹 |
| 輸入「有多少訪客」 | Bot 回傳實際訪客數字 |
| 輸入「哈哈哈」 | FallbackIntent 引導使用者 |
| 訪客計數器 | 頁面底部計數器正常顯示 |

---

## 完成後的最終架構

```
使用者瀏覽器 (HTTPS)
      │
      ▼
Cloudflare CDN（WAF + Bot Fight Mode）
      │
      ▼
AWS S3（靜態網站：HTML / CSS / JS）
      │
      ├─── fetch POST /visitor ──────► API Gateway
      │                                     │
      │                               Lambda（訪客計數）
      │                                     │
      │                               NeonDB PostgreSQL
      │
      └─── fetch POST /chat ─────────► API Gateway
                                            │
                                      Lambda（chatbot-proxy）
                                            │
                                      Amazon Lex v2（ResumeBot）
                                            │
                                      Fulfillment Lambda（chatbot-fulfillment）
                                            │
                                      回傳回應 → 前端對話框顯示
```

---

## 各步驟完成打勾

- [x] Step 1｜Amazon Lex v2 Bot 建立完成，語言設定正確（English US，Bot ID: F7MS13BUCP）
- [x] Step 2｜3 個 Intent 建立完成（GetVisitorCount / AskAboutMe / FallbackIntent）
- [x] Step 2｜Bot Build 成功，Lex 內測試通過
- [x] Step 3｜`chatbot-fulfillment` Lambda 建立，GetVisitorCount 可回傳訪客數
- [x] Step 4｜Lex Bot 串接 Fulfillment Lambda（TestBotAlias → English US），重新 Build 測試通過
- [x] Step 5｜`chatbot-proxy` Lambda 建立，IAM 權限設定完成（lex:RecognizeText）
- [x] Step 5｜API Gateway 新增 `POST /chat` 路由，部署完成（$default stage，URL: /chat）
- [x] Step 6｜前端加入 Chatbot UI，API URL 填正確（/chat，非 /prod/chat）
- [x] Step 7｜infrastructure 文件更新（iam-chatbot-policy.json）
- [x] Step 8｜saibusu.com 上線測試全部通過（"Who are you?" / "How many visitors?" 均正常）
- [x] 修正｜visitor API 加入 GET 只讀路由，chatbot 查詢不再觸發訪客計數遞增

---

> **遇到問題？** 常見卡關點：
> - Lex Build 失敗 → 確認 Sample utterance 至少填 3 條
> - Lambda 呼叫 Lex 403 → 確認 IAM Policy 的 Resource ARN 正確（Bot ID 和 Alias ID）
> - CORS 錯誤 → 確認 chatbot-proxy Lambda 的 response headers 有 `Access-Control-Allow-Origin`
> - 繁中識別率差 → 在 Lex 改用 English (US)，觸發語句改英文
