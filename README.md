# 李軒杰 — 雲端履歷網站

[![GitHub](https://img.shields.io/badge/GitHub-Saibusu-181717?logo=github)](https://github.com/Saibusu)

個人履歷靜態網站，部署於 AWS，整合 Lambda 訪客計數器與 Amazon Lex v2 智慧 Chatbot。專案原始碼：[github.com/Saibusu/MyCloudResume](https://github.com/Saibusu/MyCloudResume)

後端經歷三個版本的完整演進：

| | v1 | v2 | v3（現行）|
| :--- | :--- | :--- | :--- |
| **後端語言** | Python 3.12 | Node.js 22 | Node.js 22 + Python 3.12 |
| **資料庫** | AWS DynamoDB（NoSQL） | NeonDB（Serverless PostgreSQL） | NeonDB（Serverless PostgreSQL） |
| **ORM** | 無（直接 boto3） | Prisma ORM | Prisma ORM |
| **Chatbot** | 無 | 無 | Amazon Lex v2（ResumeBot） |
| **部署方式** | 手動上傳 | GitHub Actions 全自動 CI/CD | GitHub Actions 全自動 CI/CD |
| **連線管理** | AWS SDK 內建 | Lazy Singleton + Connection Pooler | Lazy Singleton + Connection Pooler |

---

## 專案亮點

**技術棧：AWS (S3, Lambda, API Gateway, Amazon Lex v2), NeonDB (PostgreSQL), Prisma ORM, Cloudflare WAF, Node.js / Python, GitHub Actions CI/CD**

- **智慧 Chatbot（v3 新增）**：Amazon Lex v2 ResumeBot（English US），支援訪客數查詢與個人介紹，透過 `chatbot-proxy` Lambda 串接前端（`POST /chat`），Fulfillment 由 `chatbot-fulfillment` Lambda 處理。已在 saibusu.com 驗證正常運作。
- **深層防禦實作 (Defense in Depth)**：Cloudflare WAF + S3 Bucket Policy IP 白名單（Origin Cloaking）+ API Gateway Throttling，三層聯防。
- **無伺服器架構**：v1 Lambda + DynamoDB Atomic Counter；v2/v3 Lambda + Prisma ORM + NeonDB Serverless PostgreSQL，兩種方案均解決 Race Condition 問題。
- **成本優化**：Cloudflare 取代 Route 53 DNS 管理（省 $0.50/月），Bot Fight Mode 降低 70%+ 無效流量，NeonDB 無流量自動暫停。
- **最小權限原則 (Least Privilege)**：精確配置 IAM 政策，`DATABASE_URL` 透過 GitHub Secrets + `jq` 安全注入 Lambda，避免 shell 特殊字元截斷。
- **全自動 CI/CD**：`git push` 觸發 GitHub Actions，自動完成前端、後端、環境變數、快取清除的全鏈路部署。

---

## 專案結構（v1）

> 第一版結構精簡，全為手動管理，無自動化流程。

```
├── frontend/
│   ├── index.html               # 主頁面（履歷 + 訪客計數器 UI）
│   └── photo.png                # 大頭貼
├── backend/
│   └── lambda_function.py       # Lambda 函數（Python 3.12 + boto3）
├── infrastructure/
│   ├── s3-bucket-policy.json    # S3 僅允許 Cloudflare IP 存取
│   └── iam-lambda-policy.json   # Lambda IAM Policy（僅 DynamoDB GetItem + UpdateItem）
└── README.md
```

## 專案結構（v3 現行）

> 第三版加入 Amazon Lex v2 Chatbot，完整 AI 對話整合。

```
├── frontend/
│   ├── index.html               # 主頁面（履歷 + 訪客計數器 + Chatbot UI）
│   └── photo.png                # 大頭貼
├── backend/
│   ├── index.mjs                # Lambda v2（Node.js 22 + Prisma ORM，訪客計數）
│   ├── lambda_function.py       # Lambda v1（Python + DynamoDB，保留參考）
│   ├── chatbot_fulfillment.py   # Lambda v3（Python，Lex Fulfillment）
│   └── chatbot_proxy.py         # Lambda v3（Python，API Gateway → Lex 代理）
├── prisma/
│   └── schema.prisma            # Prisma 資料模型（binaryTargets: linux-arm64）
├── infrastructure/
│   ├── s3-bucket-policy.json    # S3 僅允許 Cloudflare IP 存取
│   ├── iam-lambda-policy.json   # Lambda IAM Policy（v1 保留備考）
│   └── iam-chatbot-policy.json  # chatbot-proxy IAM Policy（lex:RecognizeText）
├── docs/
│   └── architecture-notes.md   # 完整架構技術筆記（含除錯記錄）
├── .github/workflows/
│   └── deploy.yml               # GitHub Actions 全自動部署流水線
├── package.json                 # Node.js 依賴（prisma + @prisma/client 6.6.0）
└── README.md
```

---

# v1：DynamoDB + Python Lambda

> 第一版後端使用 AWS 原生服務全家桶，驗證 Serverless 架構的核心概念。

## v1 架構

```
使用者瀏覽器
    ↓
Cloudflare（DNS + CDN + WAF + Bot Fight Mode）
    ↓ [Origin Cloaking：僅允許 Cloudflare IP]
AWS S3（靜態網站：HTML / CSS / JS / 圖片）
    ↓ [前端 fetch() GET]
AWS API Gateway（HTTP API + Throttling Rate:2 Burst:5）
    ↓ [CORS 限制：僅 saibusu.com]
AWS Lambda（Python 3.12）
    ↓ [IAM：僅 GetItem + UpdateItem]
AWS DynamoDB（Table: ResumeVisitorCount）
```

## v1 服務說明

| 服務 | 角色 | 設定重點 |
| :--- | :--- | :--- |
| **S3** | 靜態網站託管 | 開啟 Static Website Hosting |
| **Cloudflare** | CDN + DNS + WAF | 橘色雲朵 Proxy + Bot Fight Mode |
| **ACM** | SSL 憑證 | us-east-1 申請，DNS 驗證 |
| **API Gateway** | HTTP API 入口 | Throttling Rate:2 Burst:5 |
| **Lambda** | 計數邏輯 | Python 3.12，IAM 最小授權 |
| **DynamoDB** | 計數儲存 | Partition Key: `id`（String），原子操作 |
| **Route 53** | 域名管理 | 已遷移至 Cloudflare（成本優化） |

## v1 核心程式碼

```python
# backend/lambda_function.py
response = table.update_item(
    Key={'id': 'total_visits'},
    UpdateExpression='ADD #c :val',
    ExpressionAttributeNames={'#c': 'count'},
    ExpressionAttributeValues={':val': 1},
    ReturnValues="UPDATED_NEW"
)
```

DynamoDB 的 `ADD` 操作是原子的（Atomic）：資料庫在內部完成加法，不需先讀再寫，天然避免 Race Condition。

## v1 部署步驟

1. 將 `frontend/` 上傳至 S3，啟用 Static Website Hosting
2. 套用 `infrastructure/s3-bucket-policy.json`（僅允許 Cloudflare IP）
3. 建立 DynamoDB Table `ResumeVisitorCount`，Partition Key `id`（String）
4. 手動插入初始資料：`{ "id": "total_visits", "count": 0 }`
5. 建立 Lambda，上傳 `backend/lambda_function.py`，Runtime: Python 3.12
6. 套用 `infrastructure/iam-lambda-policy.json` 至 Lambda 執行角色
7. 建立 API Gateway HTTP API，GET route → 整合 Lambda
8. API Gateway Protect → Throttling：Rate 2, Burst 5
9. 建立 AWS Budgets 警報（$0.01 USD）

---

# v2：NeonDB + Prisma ORM + Node.js Lambda

> 第二版升級為關聯式資料庫 + ORM，並建立全自動 CI/CD 流水線。

## v2 架構

```
使用者瀏覽器
    ↓
Cloudflare（DNS + CDN + WAF + Bot Fight Mode）
    ↓ [Origin Cloaking：僅允許 Cloudflare IP]
AWS S3（靜態網站：HTML / CSS / JS / 圖片）
    ↓ [前端 fetch() POST /prod/visitor]
AWS API Gateway（HTTP API + Throttling Rate:2 Burst:5）
    ↓ [CORS 限制：僅 saibusu.com]
AWS Lambda（Node.js 22 + Prisma ORM 6.6.0）
    ↓ [DATABASE_URL via GitHub Secrets + jq 安全注入]
NeonDB（Serverless PostgreSQL：Visitor table）
```

## v2 服務說明

| 服務 | 角色 | 設定重點 |
| :--- | :--- | :--- |
| **S3** | 靜態網站託管 + Lambda zip 中轉 | 同時存放 `deploy/function.zip` |
| **Cloudflare** | CDN + DNS + WAF | 同 v1 |
| **API Gateway** | HTTP API POST 入口 | 同 v1 Throttling 設定 |
| **Lambda** | 計數邏輯 | Node.js 22，arm64 架構 |
| **NeonDB** | Serverless PostgreSQL | Connection Pooler 端點（`-pooler`） |
| **Prisma ORM** | 資料庫存取層 | v6.6.0，binaryTargets: linux-arm64 |
| **GitHub Actions** | CI/CD 自動部署 | 前端 + 後端 + 環境變數 + 快取清除 |

## v2 核心程式碼

```javascript
// backend/index.mjs
import { PrismaClient } from '@prisma/client'

let prisma;  // Lazy Singleton：Lambda 執行環境重用，避免重複建立連線

export const handler = async (event) => {
  if (!prisma) {
    prisma = new PrismaClient();
    // URL 由 schema.prisma url = env("DATABASE_URL") + Lambda 環境變數提供
  }

  const updatedVisitor = await prisma.visitor.update({
    where: { id: 1 },
    data: { count: { increment: 1 } },  // Prisma 原子操作，防止 Race Condition
  });

  return {
    statusCode: 200,
    headers: { "Access-Control-Allow-Origin": "*" },
    body: JSON.stringify({ count: updatedVisitor.count }),
  };
};
```

## v2 CI/CD 流水線（`deploy.yml`）

```
git push origin main
    ↓ GitHub Actions 啟動
[1] aws s3 sync ./frontend → S3（前端部署）
[2] yarn install --ignore-engines（安裝 Prisma 與依賴）
[3] rm -rf node_modules/.prisma → yarn prisma generate（產生 arm64 引擎）
[4] 清除大型工具包 → zip function.zip
[5] aws s3 cp → aws lambda update-function-code（S3 中轉）
[6] sleep 15（等待 Lambda 更新）
[7] jq 序列化 DATABASE_URL → aws lambda update-function-configuration
[8] Cloudflare Cache Purge（清除全球快取）
```

## v2 部署步驟

1. 在 NeonDB 建立 PostgreSQL 資料庫，執行初始化：
   ```sql
   CREATE TABLE "Visitor" (
     id    INTEGER PRIMARY KEY DEFAULT 1,
     count INTEGER NOT NULL DEFAULT 0
   );
   INSERT INTO "Visitor" (id, count) VALUES (1, 0);
   ```
2. 在 GitHub → Repository → Settings → Secrets → Actions 設定：

   | Secret 名稱 | 說明 |
   | :--- | :--- |
   | `AWS_ACCESS_KEY_ID` | IAM 使用者 Access Key |
   | `AWS_SECRET_ACCESS_KEY` | IAM 使用者 Secret Key |
   | `DATABASE_URL` | NeonDB 連線字串（`@` 不可編碼為 `%40`） |
   | `LAMBDA_FUNCTION_NAME` | Lambda 函數名稱 |
   | `CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID |
   | `CLOUDFLARE_API_TOKEN` | Cloudflare API Token（含快取清除權限） |

3. `git push origin main` → 自動觸發完整部署
4. API Gateway Throttling：Rate 2, Burst 5
5. AWS Budgets 警報：$0.01 USD

---

# v3：Amazon Lex v2 Chatbot 整合

## v3 架構

```
使用者瀏覽器
    ↓
Cloudflare（DNS + CDN + WAF）
    ↓
AWS S3（靜態網站 + Chatbot UI）
    ├─── POST /prod/visitor ──► API Gateway → Lambda（訪客計數 +1）→ NeonDB
    ├─── GET  /prod/visitor ──► API Gateway → Lambda（只讀計數，不遞增）→ NeonDB
    └─── POST /chat ──────────► API Gateway ($default) → chatbot-proxy → Lex v2 → chatbot-fulfillment
```

## v3 服務說明

| 服務 | 角色 | 設定重點 |
| :--- | :--- | :--- |
| **Amazon Lex v2** | NLU 引擎 | Bot: ResumeBot, en_US, Bot ID: F7MS13BUCP, Alias: TSTALIASID |
| **chatbot-fulfillment** | Lex Fulfillment | Python 3.12, arm64；GetVisitorCount 使用 GET /visitor（只讀，不遞增） |
| **chatbot-proxy** | API → Lex 代理 | Python 3.12, arm64；`lex:RecognizeText` IAM 權限 |
| **API Gateway /chat** | 新路由 | `POST /chat` on $default stage（URL 無 stage 前綴） |

## v3 上線測試結果（saibusu.com）

| 測試輸入 | Bot 回應 | 狀態 |
| :--- | :--- | :--- |
| `Who are you?` | 李軒杰個人介紹 + GitHub 連結 | ✅ |
| `How many visitors?` | 實際訪客數字（不遞增計數） | ✅ |
| 其他輸入 | FallbackIntent 引導訊息 | ✅ |
| 頁面載入 | POST /visitor 正常遞增 | ✅ |

---

## 安全設計

### Origin Cloaking（來源遮蔽）｜v1 + v2 共用

透過 Cloudflare 實作 Origin Cloaking（來源遮蔽）。除了設定橘色雲朵隱藏後端節點，更在 AWS S3 套用了僅允許 Cloudflare IP 區段的 Bucket Policy，確保所有流量都必須先經過 Cloudflare WAF 過濾，徹底杜絕繞過 CDN 直接攻擊 S3 的可能性。

```
攻擊者直接請求 S3 URL
    ↓
S3 Bucket Policy 比對來源 IP
    ↓ 非 Cloudflare IP → 403 Forbidden
    ↓ Cloudflare IP   → 正常回應
```

| 防護層 | 實作方式 | 版本 |
| :--- | :--- | :--- |
| DNS 遮蔽 | Cloudflare Proxy（橘色雲朵），隱藏真實 S3 endpoint | v1 + v2 |
| IP 白名單 | S3 Bucket Policy 僅允許 15 個 Cloudflare IP 區段 | v1 + v2 |
| WAF 過濾 | 所有請求強制經過 Cloudflare WAF 才能到達 S3 | v1 + v2 |

### API Gateway Throttling（節流）｜v1 + v2 共用

設定速率限制（Rate: 2）與高載限制（Burst: 5），從基礎設施層級防止 Lambda 與資料庫被惡意刷量攻擊。當請求超過限制時，API Gateway 直接回傳 `429 Too Many Requests`，確保後端不會因惡意流量而產生非預期費用。

| 設定項目 | 數值 | 防禦目標 |
| :--- | :--- | :--- |
| Rate Limit | 2 req/s | 防止穩定速率的暴力請求 |
| Burst Limit | 5 req | 防止瞬間爆量耗盡 Lambda 並發額度 |
| 回應碼 | 429 Too Many Requests | 明確告知攻擊者已被限流 |

### Lambda CORS 限制｜v1 + v2 共用

設定 `Access-Control-Allow-Origin` 僅允許來自 `https://saibusu.com` 的跨域請求（v1），v2 因 API Gateway 配置調整為 `*`（配合 Cloudflare WAF 在更前層做來源過濾）。

### IAM 最小權限原則｜v1

Lambda 執行角色僅授予對特定資料表的 `dynamodb:GetItem` 與 `dynamodb:UpdateItem`，禁止 `Scan`、`DeleteItem` 或存取其他資料表，確保即便程式碼存在漏洞，攻擊者也無法藉此橫向移動至其他 AWS 資源。

```json
{
  "Action": ["dynamodb:GetItem", "dynamodb:UpdateItem"],
  "Resource": "arn:aws:dynamodb:...:table/ResumeVisitorCount"
}
```

### DATABASE_URL 安全注入｜v2 新增

`DATABASE_URL` 儲存於 GitHub Secrets，部署時透過 `jq` 將連線字串序列化為合法 JSON，再注入 Lambda 環境變數，避免連線字串中的 `&`、`@` 等特殊字元被 shell 截斷導致資料庫連線失敗。

```yaml
# deploy.yml 關鍵步驟
DB_URL="${{ secrets.DATABASE_URL }}"
NEW_VARS=$(jq -n --arg db "$DB_URL" '{"Variables":{"DATABASE_URL":$db}}')
aws lambda update-function-configuration --environment "$NEW_VARS"
```

### Cloudflare WAF 與 Bot 防護｜v1 + v2 共用

在 CDN 層級實作了 Cloudflare WAF 自訂規則與 Bot Fight Mode，有效降低了 70% 以上的自動化掃描流量。透過定期分析 Security Events 日誌，能主動監控並應對針對性攻擊。

| 防護機制 | 效果 | 版本 |
| :--- | :--- | :--- |
| **WAF 自訂規則** | 攔截惡意請求模式與異常 User-Agent | v1 + v2 |
| **Bot Fight Mode** | 自動化掃描流量降低 70%+ | v1 + v2 |
| **API Throttling** | Rate: 2 / Burst: 5，阻斷 API 暴力請求 | v1 + v2 |
| **Security Events 日誌** | 主動監控，快速識別針對性攻擊 | v1 + v2 |
| **成本安全** | 限流 + Bot 過濾確保 AWS 帳單維持在免費額度內；v1 DynamoDB 依賴此機制，v2 NeonDB 有無流量自動暫停補強 | v1 為主，v2 延續 |
| **jq 安全注入** | 環境變數含特殊字元時透過 jq 序列化，防止 shell injection | v2 新增 |
