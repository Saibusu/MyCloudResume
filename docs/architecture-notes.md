# saibusu.com 雲端架構技術筆記

> 本筆記為 **saibusu.com** 雲端履歷專案的完整技術深度彙整，涵蓋 Serverless 架構實作與深層防禦（Defense in Depth）的完整流程解析。

---

## 目錄

**v1 架構（DynamoDB + Python Lambda）**
1. [Amazon S3 靜態網站託管與來源遮蔽（Origin Cloaking）](#v1-s3)
2. [Cloudflare 邊緣計算層與多層防禦體系](#v1-cloudflare)
3. [AWS API Gateway 流量控管與 Throttling 機制](#v1-api-gateway)
4. [AWS Lambda 運算邏輯與 DynamoDB 原子操作](#v1-lambda)
5. [GitHub Actions CI/CD 與自動化快取清除](#v1-cicd)

**v2 升級（NeonDB + Prisma ORM + Node.js Lambda）**

6. [為什麼要遷移？](#v2-migrate)
7. [新技術說明（NeonDB / Prisma ORM / Lazy Singleton）](#v2-new-tech)
8. [GitHub Actions v2 全自動部署流水線](#v2-cicd-pipeline)
9. [除錯記錄：CI/CD 層 — 10 次 Actions 紅燈](#v2-cicd-errors)
10. [除錯記錄：Runtime 層 — Actions 通過但訪客計數器仍失敗](#v2-runtime-errors)

**本機開發環境**

11. [本機環境建置與 Prisma 7 本地探索記錄](#local-env)

---

<a id="v1-s3"></a>

## 步驟一：Amazon S3 靜態網站託管與來源遮蔽（Origin Cloaking）

### 詳細處理與用途

Amazon S3（Simple Storage Service）在這個架構中擔任「基礎設施底層」，負責存放履歷的所有前端靜態資源（HTML、CSS、JS 與圖片）。與傳統使用虛擬機（EC2）架設 Web Server（如 Apache 或 Nginx）不同，S3 是無伺服器（Serverless）的物件存儲服務，這意味著不需要管理作業系統更新或維補，且具備極高的可用性與極低的成本。

在處理上，將 `frontend/` 資料夾上傳至 S3 儲存桶，並啟用了「靜態網站託管」功能，將 S3 轉化為一個可以透過 HTTP 存取的網頁空間。

### 交互作用與資安細節

最關鍵的處理在於 **Origin Cloaking（來源遮蔽）**。為了防止攻擊者直接掃描並攻擊 S3 的原始 URL，配置了 **S3 Bucket Policy**，這是最核心的資安防線之一。透過 `IpAddress` 條件限制，僅允許 Cloudflare 官方提供的 15 個全球 IP 區段進行 `s3:GetObject` 存取。

```json
{
  "Condition": {
    "IpAddress": {
      "aws:SourceIp": [
        "173.245.48.0/20", "103.21.244.0/22", "..."
      ]
    }
  }
}
```

這種設計強迫所有使用者流量必須先經過 Cloudflare 的 CDN 與 WAF 過濾，任何試圖繞過 Cloudflare 直接連接 S3 的請求都會收到 `403 Forbidden` 錯誤。

```
攻擊者直接請求 S3 URL
    ↓
S3 Bucket Policy 比對來源 IP
    ↓ 非 Cloudflare IP → 403 Forbidden
    ↓ Cloudflare IP   → 正常回應
```

---

<a id="v1-cloudflare"></a>

## 步驟二：Cloudflare 邊緣計算層與多層防禦體系

### 詳細處理與用途

Cloudflare 在此架構中扮演「大門守衛」的角色，提供 DNS 解析、CDN 全球快取與 WAF（Web Application Firewall）三重防禦。由於已將網域 `saibusu.com` 從 AWS Route 53 移轉至 Cloudflare 代管，這不僅優化了每月 **$0.50 USD** 的管理成本，更讓所有流量在進入 AWS 前即可被過濾。

開啟「橘色雲朵」Proxy 模式，隱藏了真實 S3 終端路徑，讓外界只能看到 Cloudflare 的 IP。此外，啟用了 **Bot Fight Mode**，利用其大數據模型自動攔截惡意爬蟲，有效降低 70%+ 的無效流量。

### 交互作用與細節實作

進一步實作了 **Managed Challenge（受管理挑戰）** 規則。當訪客存取首頁 `/` 時，Cloudflare 會根據行為模式進行靜默檢查：

- **正常人類訪客** → 過程幾乎無感，直接通過
- **自動化攻擊腳本** → 要求通過驗證碼挑戰

這與後端的 AWS API Gateway 形成協同防禦：Cloudflare 負責阻斷大部分的「背景噪音」流量，確保 AWS Lambda 不會因惡意爬蟲頻繁呼叫而產生不必要費用。「邊緣端攔截」策略是資安工程中成本效益最高的一環，因為它在攻擊抵達付費資源前就已將其消除。

---

<a id="v1-api-gateway"></a>

## 步驟三：AWS API Gateway 流量控管與 Throttling 機制

### 詳細處理與用途

當使用者的瀏覽器載入履歷網頁時，前端 JavaScript 會發送一個非同步請求（fetch）到 AWS API Gateway。API Gateway 擔任「門面」的角色，負責接收 HTTP 請求並轉發給後端 Lambda 執行。

選擇使用 **HTTP API**（比傳統 REST API 更輕量、延遲更低且成本更節省），並實作了 **Throttling（節流）** 設定：

| 參數 | 值 | 說明 |
|------|-----|------|
| Rate | 2 req/s | 每秒穩定處理的請求上限 |
| Burst | 5 req | 允許的瞬間峰值請求數 |

### 交互作用與防禦深度

這項設定直接對應資安中的「**資源耗盡攻擊（Resource Exhaustion）**」防禦。若有人以 `while(true)` 迴圈不斷刷新頁面試圖耗盡 Lambda 免費額度，Throttling 會在第一時間攔截並回傳 `429 Too Many Requests`。

此外，配置了 **CORS（跨來源資源共用）** 限制，僅允許來自 `https://saibusu.com` 的請求，有效防止其他惡意網站偽造請求呼叫 API。

---

<a id="v1-lambda"></a>

## 步驟四：AWS Lambda 運算邏輯與 DynamoDB 原子操作

### 詳細處理與用途

後端邏輯完全由 AWS Lambda（Python 3.12）處理，採用事件驅動的無伺服器運算模式。

訪客計數的關鍵技術點在於 **DynamoDB Atomic Counter（原子計數器）**：

```python
response = table.update_item(
    Key={'id': 'total_visits'},
    UpdateExpression='ADD #c :val',
    ExpressionAttributeNames={'#c': 'count'},
    ExpressionAttributeValues={':val': 1},
    ReturnValues="UPDATED_NEW"
)
```

| 方式 | 問題 |
|------|------|
| 先讀取 → Lambda 加一 → 存回 | ❌ 併發時產生 Race Condition，計數失準 |
| DynamoDB `ADD` 原子操作 | ✅ 資料庫內部完成，保證準確性 |

### 交互作用與權限配置

貫徹 **Least Privilege（最小權限原則）**，IAM Policy 僅授予 Lambda 對特定表格的最小必要操作：

```json
{
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:UpdateItem"
  ],
  "Resource": "arn:aws:dynamodb:...:table/ResumeVisitorCount"
}
```

這確保了即便 Lambda 程式碼存在漏洞，攻擊者也無法利用該角色去存取或破壞其他 AWS 資源。

---

<a id="v1-cicd"></a>

## 步驟五：GitHub Actions CI/CD 與自動化快取清除

### 詳細處理與用途

將原本手動上傳的流程轉化為全自動化的 **CI/CD 流水線**。當執行 `git push` 時，自動觸發以下流程：

```
git push → GitHub Actions 啟動
    ↓
Ubuntu 環境初始化
    ↓
使用 GitHub Secrets 中的 AWS 金鑰
    ↓
aws s3 sync ./frontend s3://saibusu.com --delete
    ↓
Cloudflare Cache Purge（清除全球邊緣節點快取）
```

`.github/workflows/deploy.yml` 核心配置：

```yaml
- name: Deploy frontend to S3
  run: |
    aws s3 sync ./frontend s3://saibusu.com --delete
```

### 交互作用與全局同步

最後一塊拼圖是 **Cloudflare Cache Purge（清除快取）**。由於 Cloudflare 在全球邊緣節點快取 HTML，不主動清除的話訪客可能會看到舊版網頁數小時。部署腳本的最後步驟會透過 Cloudflare API Token 自動發送清除指令，讓全球節點快取同步失效並重新抓取新版內容。

| 指標 | 手動部署 | CI/CD 自動化 |
|------|---------|------------|
| 部署時間 | ~5 分鐘 | ~30 秒 |
| 人為疏失風險 | 高 | 極低 |
| 版本一致性 | 不保證 | 完全一致 |
| 符合業界標準 | ❌ | ✅ GitOps / IaC |

---

## 架構全貌

```
使用者瀏覽器
    ↓
Cloudflare（DNS + CDN + WAF + Bot Fight Mode）
    ↓ [Origin Cloaking：僅允許 Cloudflare IP]
AWS S3（靜態網站：HTML / CSS / JS / 圖片）
    ↓ [前端 fetch()]
AWS API Gateway（HTTP API + Throttling Rate:2 Burst:5）
    ↓ [CORS 限制：僅 saibusu.com]
AWS Lambda（Python 3.12：訪客計數邏輯）
    ↓ [IAM Least Privilege]
AWS DynamoDB（Atomic Counter：ResumeVisitorCount）
```

## 防禦層次總覽

| 層次 | 技術 | 防禦目標 |
|------|------|---------|
| DNS 層 | Cloudflare Proxy | 隱藏真實 IP，防止直連攻擊 |
| 邊緣層 | WAF + Bot Fight Mode | 攔截惡意掃描與爬蟲（降低 70%+） |
| 網路層 | S3 Bucket Policy IP 白名單 | 強制流量必須經過 Cloudflare |
| API 層 | API Gateway Throttling | 防止資源耗盡攻擊（429） |
| 應用層 | CORS 限制 | 防止跨站偽造請求 |
| 資料層 | IAM Least Privilege | 最小化資料洩漏爆炸半徑 |
| 財務層 | AWS Budgets $0.01 警報 | 異常帳單即時通知 |

---

## 技術概念深度補充

### 核心運算與內容傳遞：EC2、CDN 與 Lambda

#### 1. EC2（Elastic Compute Cloud）

EC2 是 AWS 提供的虛擬機服務，屬於 **IaaS（Infrastructure as a Service）**。它讓你擁有完整的作業系統控制權，可自定義 CPU、記憶體，並在上面執行任何軟體（如 Nginx、Docker）。

**與本專案的比較：**

| 項目 | EC2 | Lambda（本專案採用）|
|------|-----|------------------|
| 服務模型 | IaaS（管理作業系統） | FaaS（只管程式碼） |
| 計費方式 | 24 小時開機費用 | 按執行次數計費 |
| 適用場景 | 長時間運行、複雜環境配置 | 流量不固定、邏輯簡單 |
| 維護成本 | 高（需更新 OS、安全補丁） | 極低（AWS 全權管理） |

雖然本專案最終選擇 S3 + Lambda 的 Serverless 架構，但在需要長時間運行或特定環境配置的應用（例如 Django 後端、容器化服務）時，EC2 仍是首選。

---

#### 2. CDN（Content Delivery Network）— Cloudflare

CDN 的核心目標是「**物理加速**」。它在全球佈署數百個邊緣節點（Edge Nodes）。

```
台灣訪客請求 saibusu.com
    ↓
連到距離最近的 Cloudflare 台北節點（< 10ms）
    ↓（快取命中）→ 直接回應，不經 AWS
    ↓（快取失效）→ 向美國 S3 抓取新版本
```

CDN 不僅加速，還具備「緩衝」作用。它會快取靜態網頁（HTML/CSS）。當更新網頁並執行 GitHub Actions 時，腳本會觸發 **Purge Cache**，強迫 CDN 丟棄舊版並向 S3 抓取新版，確保訪客永遠看到最新內容。

---

### 安全防護層：WAF 與 Managed Challenge

#### 3. WAF（Web Application Firewall）

WAF 運作在 **OSI 七層模型的第七層（應用層）**。它不像傳統防火牆只看 IP 與 Port，WAF 會深度檢查請求內容：

| 攻擊類型 | WAF 的處理方式 |
|---------|--------------|
| SQL Injection | 偵測 SQL 關鍵字（如 `DROP TABLE`）並封鎖 |
| XSS（跨站腳本） | 偵測惡意 `<script>` 注入 |
| 惡意機器人 | 根據 User-Agent 特徵識別並攔截 |
| 無瀏覽器特徵的腳本 | 攔截沒有正常瀏覽器標頭的 Python/curl 請求 |

在本專案中，Cloudflare 自訂 WAF 規則能根據請求的 Header 判斷是否為惡意機器人，例如直接擋掉沒有瀏覽器特徵（User-Agent）的自動化腳本。

---

#### 4. Managed Challenge（受管理挑戰）

這是一種「**非對稱**」的防禦手段。當 WAF 懷疑某個請求有問題時，不直接封鎖，而是發起「挑戰」：

```
可疑請求抵達 Cloudflare
    ↓
Cloudflare 發送 JavaScript 挑戰
    ↓ 人類瀏覽器 → 自動執行（通常無感，< 1 秒）→ 放行
    ↓ 攻擊腳本   → 無法執行 JS / 通過圖示驗證 → 封鎖
```

**為什麼這是「非對稱」的？**
攻擊者需要花大量資源（真實瀏覽器環境、驗證碼識別 AI）才能繞過，而正常用戶幾乎零成本通過。這種設計讓「攻擊成本遠高於防禦成本」，能有效過濾 70%+ 的自動化背景雜訊。

---

### 流量與溝通控管：Throttling 與 CORS

#### 5. Throttling（節流）

這是在 API Gateway 層級實作的「資源配給」制度：

```
Rate: 2  → 每秒穩定處理 2 個請求
Burst: 5 → 允許瞬間最多 5 個請求的突發峰值
超過上限  → 回傳 429 Too Many Requests
```

**為什麼這對錢包很重要？**

Lambda 是按量計費。若沒有 Throttling，攻擊者只需一個 `while True: requests.get(api_url)` 腳本就能在幾分鐘內耗盡免費額度，產生意外帳單。Throttling 在 API Gateway 層直接截斷，Lambda 甚至不會被啟動，實現了**在付費資源前的最後一道防線**。

| 攻擊情境 | 無 Throttling | 有 Throttling |
|---------|-------------|--------------|
| 每秒 100 次請求 | Lambda 被呼叫 100 次，產生費用 | 第 3 次起回傳 429，Lambda 僅執行 2 次 |
| 財務風險 | 高 | 極低 |

---

#### 6. CORS（Cross-Origin Resource Sharing）

CORS 是**瀏覽器的安全機制**。預設情況下，網頁上的 JS 不允許跨網域存取 API。

```
saibusu.com 的 JS 呼叫 execute-api.us-east-1.amazonaws.com
    ↓
瀏覽器先發送 OPTIONS 預檢請求（Preflight）
    ↓ API Gateway 回傳 Access-Control-Allow-Origin: https://saibusu.com
    ↓ 來源符合 → 允許正式請求
    ↓ 來源不符 → 瀏覽器直接封鎖，不發送正式請求
```

**為什麼需要限制來源？**

若沒有正確設定 CORS 限制，任何第三方網站都可以寫一段 JS 呼叫你的 API：

```javascript
// 惡意網站 evil.com 的腳本（若無 CORS 限制）
fetch('https://你的API.execute-api.amazonaws.com/')
  .then(r => r.json())
  .then(data => console.log(data)); // 成功讀取你的計數器
```

透過將 `Access-Control-Allow-Origin` 鎖定為 `https://saibusu.com`，任何其他網域的請求都會被瀏覽器在本地端直接阻擋，達到**防止 API 盜用與流量消耗**的效果。

---

# 後端架構升級：NeonDB + Prisma ORM + Node.js（v2）

> 本章記錄將後端從 **AWS DynamoDB + Python Lambda** 遷移至 **NeonDB Serverless PostgreSQL + Prisma ORM + Node.js Lambda** 的完整過程，包含所有遇到的錯誤、根本原因分析與修正方法。

---

<a id="v2-migrate"></a>

## 為什麼要遷移？

| 面向 | v1 DynamoDB + Python | v2 NeonDB + Prisma |
| :--- | :--- | :--- |
| 資料庫類型 | NoSQL（鍵值對） | 關聯式 PostgreSQL |
| 查詢能力 | 有限（只有 GetItem/UpdateItem） | 完整 SQL 能力 |
| ORM 支援 | 無（直接呼叫 boto3） | Prisma ORM（型別安全） |
| 學習目標 | AWS 原生服務整合 | ORM 概念、SQL、現代後端實踐 |
| 冷啟動效能 | 極快（boto3 輕量） | 稍慢（Prisma 引擎初始化） |

---

<a id="v2-new-tech"></a>

## 新技術說明

### NeonDB（Serverless PostgreSQL）

**用途：** 提供 PostgreSQL 資料庫，專為 Serverless 環境優化。

**核心特性：**
- **Serverless Auto-Scaling**：無流量時資料庫自動暫停，有請求時自動喚醒，費用接近零
- **Connection Pooling**：提供 `-pooler` 後綴的連線端點，專門處理 Serverless 環境下的短暫連線，避免連線數耗盡
- **分支功能（Branch）**：可建立資料庫快照分支，用於開發環境測試

**連線字串格式：**
```
postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

**交互作用：** Lambda 透過 Prisma ORM 發送 SQL 語句至 NeonDB。每次 Lambda 執行約建立一個連線，執行完畢後連線歸還至 Pooler，不會長期佔用。

---

### Prisma ORM（Object-Relational Mapping）

**用途：** 讓 JavaScript/TypeScript 程式碼用物件操作資料庫，不需要手寫 SQL。

**運作方式：**
```
index.mjs 呼叫 prisma.visitor.update()
    ↓
Prisma ORM 翻譯為 SQL
    → UPDATE "Visitor" SET count = count + 1 WHERE id = 1
    ↓
透過連線字串傳送至 NeonDB PostgreSQL
    ↓
回傳更新後的資料列
```

**核心概念：**

| 概念 | 說明 |
| :--- | :--- |
| `schema.prisma` | 定義資料模型（等同於資料庫 Schema） |
| `prisma generate` | 根據 schema 產生型別安全的 Client 程式碼 |
| `PrismaClient` | 實際執行資料庫操作的物件 |
| `binaryTargets` | 指定 Prisma 引擎的編譯目標平台 |

**`schema.prisma` 說明：**
```prisma
generator client {
  provider      = "prisma-client-js"
  binaryTargets = ["native", "linux-arm64-openssl-3.0.x"]
  // native：本機開發用
  // linux-arm64-openssl-3.0.x：Lambda arm64 架構用
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")  // 從環境變數讀取，不 hardcode
}

model Visitor {
  id    Int @id @default(1)  // 固定 id=1，單一計數列
  count Int @default(0)
}
```

**為什麼需要 `binaryTargets`？**
Prisma 的查詢引擎是編譯好的二進位檔（`.node`）。Lambda 執行環境是 Linux arm64，本機開發是 Windows/macOS x64，兩者架構不同，必須明確指定兩個目標才能讓 `prisma generate` 產生兩份引擎，部署時 Lambda 才能找到對應的引擎執行。

---

### Lazy Singleton 模式（Lambda 連線優化）

```javascript
let prisma;  // 在 handler 外宣告

export const handler = async (event) => {
  if (!prisma) {
    prisma = new PrismaClient();  // 只在第一次執行時初始化
  }
  // 後續請求重複使用同一個 prisma 實例
};
```

**原理：** Lambda 執行環境（Execution Environment）在同一個容器內會被重複使用（Warm Start）。將 `prisma` 宣告在 handler 外層，使其在容器生命週期內只初始化一次，避免每次請求都建立新的資料庫連線，大幅降低延遲與 NeonDB 連線消耗。

---

<a id="v2-cicd-pipeline"></a>

### GitHub Actions CI/CD 全自動部署流水線

**完整流程：**
```
git push origin main
    ↓
GitHub Actions 啟動（ubuntu-latest）
    ↓
[1] S3 前端部署：aws s3 sync ./frontend s3://saibusu.com --delete
    ↓
[2] yarn install --ignore-engines（安裝 Prisma 與依賴）
    ↓
[3] rm -rf node_modules/.prisma → yarn prisma generate（產生 arm64 引擎）
    ↓
[4] 清理大型工具包 → zip -r function.zip index.mjs node_modules
    ↓
[5] aws s3 cp function.zip → aws lambda update-function-code（S3 中轉）
    ↓
[6] sleep 15（等待 Lambda 代碼更新完成）
    ↓
[7] jq 安全序列化 DATABASE_URL → aws lambda update-function-configuration
    ↓
[8] Cloudflare Cache Purge（清除全球快取）
```

**為什麼要用 S3 中轉部署 Lambda？**
直接上傳 zip 至 Lambda 有 50MB 限制（API 直傳），而包含 Prisma 引擎的 `function.zip` 約 18MB，雖然在限制內，但透過 S3 中轉可支援最大 250MB，且更穩定可靠。

**為什麼用 `sleep 15` 而非 `aws lambda wait`？**
`aws lambda wait function-updated` 需要 `lambda:GetFunctionConfiguration` 權限，但最小權限原則下的 IAM 角色沒有此授權。改用 `sleep 15` 等待 Lambda 更新完成，避免增加不必要的 IAM 權限。

---

## 遇到的錯誤與修正記錄

> 錯誤分為兩大類型：
> - **【CI/CD 層】** GitHub Actions 工作流程本身失敗（Actions 紅燈，部署未完成）
> - **【Runtime 層】** Actions 成功部署，但 Lambda 執行時回傳錯誤（訪客計數器無法運作）

---

<a id="v2-cicd-errors"></a>

### CI/CD 層：GitHub Actions 工作流程失敗記錄（10 次紅燈）

從 v2 遷移開始（凌晨 12:50）到首次完整部署成功（凌晨 2:05），共歷經 **10 次 CI/CD 工作流程失敗**。以下按 commit 順序記錄每次失敗的原因與處置：

| # | Commit 訊息 | 失敗位置 | 根本原因 |
| :--- | :--- | :--- | :--- |
| 1 | `feat: migrate backend to NeonDB + Prisma ORM` | `yarn install` / `prisma generate` | 初次遷移，未設定 binaryTargets，Prisma 無法找到 Lambda 對應引擎 |
| 2 | `fix: upgrade actions version and sync yarn.lock` | `yarn install` | `yarn.lock` 鎖定的套件版本與新環境不一致，依賴解析衝突 |
| 3 | `fix: upgrade node version to 22 for prisma compatibility` | `yarn install` | Actions runner 使用 Node 16/18，Prisma 7 需要 Node.js 18+，版本不符 |
| 4 | `fix: force re-generate prisma client with clean slate` | `prisma generate` | 舊版 Prisma Client 快取殘留，`node_modules/.prisma` 沒有清除，讀到舊引擎 |
| 5 | `chore: align prisma versions to 7.6.0 and sync lockfile` | `prisma generate` | `prisma`（CLI）與 `@prisma/client`（runtime）版本不一致，generate 失敗 |
| 6 | `fix: restore yarn install and clean up prisma generation` | `zip` / Lambda 上傳 | `node_modules` 清理過度，打包時缺少必要依賴，Lambda zip 結構錯誤 |
| 7 | `fix: align prisma engines for lambda arm64` | Lambda 執行時 | `binaryTargets` 未包含 `linux-arm64-openssl-3.0.x`，Lambda 找不到引擎二進位檔 |
| 8 | `fix: move connection url to prisma.config.ts for Prisma 7 compatibility` | `prisma generate` | Prisma 7 完全廢除 `schema.prisma` 的 `url` 欄位，產生 `P1012` 驗證錯誤 |
| 9 | `fix: use s3 as intermediate for large lambda deployment` | `aws lambda update-function-code` | 打包後 zip 超過 Lambda API 直傳 50MB 限制，改用 S3 中轉才解決 |
| 10 | `final: restrict IAM to specific lambda ARN and deploy` | `aws lambda wait` | `aws lambda wait function-updated` 需要 `GetFunctionConfiguration` 權限，IAM 使用者未授權 |

---

#### 失敗 1：架構不匹配（初次遷移）

**問題：** 首次提交 v2 時，`schema.prisma` 未設定 `binaryTargets`，Prisma 只產生本機（Windows/macOS）引擎，部署到 Linux ARM64 的 Lambda 時找不到可執行的引擎檔案。

**學習點：** Prisma 的查詢引擎是**平台相關的編譯二進位檔**，跨環境部署必須明確指定目標平台。

---

#### 失敗 2：`yarn.lock` 依賴衝突

**問題：** 舊的 `yarn.lock` 鎖定了特定的依賴樹版本，當 `package.json` 更新 Prisma 版本後，lockfile 與新版本不相容，導致 `yarn install` 解析失敗。

**修正：** 刪除 `yarn.lock`，讓 CI 環境重新產生對應版本的 lockfile。

---

#### 失敗 3：Node.js 版本不符

**問題：** GitHub Actions 預設使用的 Node.js 版本過舊（Node 16），而 Prisma 7 要求 Node.js 18+。

**修正：** 在 `deploy.yml` 明確設定 `node-version: '22'`：
```yaml
- uses: actions/setup-node@v3
  with:
    node-version: '22'
```

---

#### 失敗 4：Prisma Client 快取污染

**問題：** 先前已 generate 的舊版 Prisma Client 殘留在 `node_modules/.prisma`，新的 `prisma generate` 沒有完整重建，CI 環境讀到舊引擎導致部署的 Lambda 行為異常。

**修正：** 在 CI 步驟加入清除指令：
```bash
rm -rf node_modules/.prisma
yarn prisma generate
```

---

#### 失敗 5：Prisma CLI 與 Client 版本不一致

**問題：** `devDependencies` 的 `prisma`（CLI）版本與 `dependencies` 的 `@prisma/client`（runtime）版本不一致（例如 CLI 是 7.5.0，Client 是 7.6.0），`prisma generate` 產生的 Client 與 runtime 不相容。

**修正：** 確保兩者版本完全一致：
```json
"dependencies":    { "@prisma/client": "6.6.0" },
"devDependencies": { "prisma":          "6.6.0" }
```

---

#### 失敗 6：打包結構錯誤 / node_modules 缺失

**問題：** 過度清理 `node_modules`，或是 zip 打包時路徑錯誤（把整個 `backend/` 資料夾包進去），導致 Lambda 找不到根目錄的 `index.mjs` 或缺少 `node_modules`。

**錯誤訊息（Lambda 執行時）：**
```
Runtime.ImportModuleError: Error: Cannot find module 'index'
```

**修正：** 確保 zip 從正確目錄打包，`index.mjs` 必須在 zip 的根目錄：
```bash
cd backend
zip -r ../function.zip index.mjs ../node_modules
```

---

#### 失敗 7：Lambda arm64 引擎缺失

**問題：** Lambda 執行架構設定為 `arm64`（Graviton2，效能更好且成本較低），但 `binaryTargets` 只有 `native`（本機），沒有包含 `linux-arm64-openssl-3.0.x`，Lambda 啟動時找不到對應的 Prisma 查詢引擎。

**錯誤訊息（Lambda 執行時）：**
```
PrismaClientInitializationError: Query engine binary for current platform 
"linux-arm64-openssl-3.0.x" could not be found.
```

**修正：** `schema.prisma` 加入 arm64 目標：
```prisma
generator client {
  provider      = "prisma-client-js"
  binaryTargets = ["native", "linux-arm64-openssl-3.0.x"]
}
```

---

#### 失敗 8：Prisma 7 破壞性升級（url 欄位廢除）

**問題：** `package.json` 安裝了 Prisma 7，但 Prisma 7 完全廢除了 `schema.prisma` 的 `url` 欄位，改為強制使用 `prisma.config.ts`。`prisma generate` 階段直接報 `P1012` 驗證錯誤，CI 流程中止。

**錯誤訊息：**
```
Error: The datasource property `url` is no longer supported in schema files.
Move connection URLs for Migrate to `prisma.config.ts`
Prisma CLI Version : 7.6.0
```

**根本問題：** `prisma.config.ts` 是提供給 CLI（migrate/studio）使用的，Lambda **執行時**無法讀取此檔案，形成無法解決的死結。

**修正：** 降版至 **Prisma 6.6.0**，刪除 `prisma.config.ts`，恢復在 `schema.prisma` 設定 `url = env("DATABASE_URL")`：
```json
"dependencies":    { "@prisma/client": "6.6.0" },
"devDependencies": { "prisma":          "6.6.0" }
```

---

#### 失敗 9：Lambda zip 超過直傳大小限制

**問題：** 包含 Prisma 引擎的 `function.zip` 體積過大，超過 Lambda API 直傳的 50MB 限制（雖實際約 18MB，仍選擇 S3 中轉以確保穩定性）。

**修正：** 改為 S3 中轉部署：
```bash
aws s3 cp function.zip s3://$BUCKET/deploy/function.zip
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION_NAME \
  --s3-bucket $BUCKET \
  --s3-key deploy/function.zip
```

| 方式 | 大小上限 | 穩定性 |
| :--- | :--- | :--- |
| Lambda API 直傳 | 50 MB | 一般 |
| S3 中轉上傳 | 250 MB | 高 |

---

#### 失敗 10：IAM 權限不足（`aws lambda wait` 指令）

**問題：** `deploy.yml` 使用 `aws lambda wait function-updated` 等待 Lambda 更新完成，但此指令內部會不斷呼叫 `GetFunctionConfiguration` 輪詢狀態，而 IAM 使用者的政策只授予了 `UpdateFunctionCode` 與 `UpdateFunctionConfiguration`，沒有 `GetFunctionConfiguration`，Actions 因 `AccessDeniedException` 中斷。

**錯誤訊息：**
```
User: arn:aws:iam::...:user/GitHub-Actions-S3-Deploy is not authorized
to perform: lambda:GetFunctionConfiguration on resource: ...
```

**修正選擇：**
| 方案 | 說明 | 決定 |
| :--- | :--- | :--- |
| 增加 IAM 權限 | 加 `GetFunctionConfiguration` | 違反最小權限，不採用 |
| 改用 sleep | `sleep 15` 替代 wait | ✅ 採用 |

```yaml
# 改為
- run: sleep 15
```

---

<a id="v2-runtime-errors"></a>

### Runtime 層：Actions 通過但訪客計數器仍失敗

從 commit #15（凌晨 2:05）起，GitHub Actions 工作流程開始出現藍色勾號（成功），代表 CI/CD 流水線本身已正常運作（程式碼打包、Lambda 更新、S3 部署均完成）。

但開啟瀏覽器造訪 `saibusu.com` 時，訪客計數器區塊顯示「訪客計數器暫時離線」，Lambda 回傳 JSON 錯誤：
```json
{ "error": "DB_FAIL", "message": "..." }
```

這代表**部署層**已正常，問題出在**Lambda 執行層**：程式碼邏輯、Prisma 建構子語法、資料庫連線字串解析等。以下記錄 6 個 Runtime 層錯誤：

---

### 錯誤 1：`Unknown property datasources provided to PrismaClient constructor`

**錯誤訊息：**
```
Unknown property datasources provided to PrismaClient constructor.
```

**根本原因：** 使用了 Prisma 5 的舊語法 `new PrismaClient({ datasources: { db: { url: ... } } })`，Prisma 6/7 已移除此參數。

**修正：**
```javascript
// ❌ 錯誤（Prisma 5 舊語法）
prisma = new PrismaClient({
  datasources: { db: { url: process.env.DATABASE_URL } }
});

// ✅ 正確（Prisma 6）
prisma = new PrismaClient();
// URL 由 schema.prisma 的 url = env("DATABASE_URL") + Lambda 環境變數提供
```

---

### 錯誤 2：`PrismaClient needs to be constructed with a non-empty, valid PrismaClientOptions`

**錯誤訊息：**
```
PrismaClient needs to be constructed with a non-empty, valid PrismaClientOptions
```

**根本原因：** `schema.prisma` 缺少 `url = env("DATABASE_URL")`，Prisma 不知道要連哪個資料庫，呼叫 `new PrismaClient()` 時無從驗證配置。

**修正：** 在 `schema.prisma` 的 `datasource db` 區塊補上 `url = env("DATABASE_URL")`。

---

### 錯誤 3：Prisma 7 完全廢除 schema.prisma 的 `url` 欄位

**錯誤訊息：**
```
Error: The datasource property `url` is no longer supported in schema files.
Move connection URLs for Migrate to `prisma.config.ts`
```

**根本原因：** `package.json` 使用了 Prisma 7，但 Prisma 7 是破壞性升級，完全移除了 `schema.prisma` 的 `url` 欄位，改為強制使用 `prisma.config.ts`（TypeScript 配置文件）。但 `prisma.config.ts` 只供 CLI 使用，Lambda 執行時無法讀取，造成死結。

**修正：** 降回 **Prisma 6.6.0**，同時刪除 `yarn.lock` 讓 CI 重新產生對應版本的 lockfile：
```json
// package.json
"dependencies": { "@prisma/client": "6.6.0" },
"devDependencies": { "prisma": "6.6.0" }
```

**版本演進對照：**
| Prisma 版本 | `schema.prisma url` | 建構子語法 |
| :--- | :--- | :--- |
| v4 / v5 | ✅ 支援 | `new PrismaClient({ datasources: { db: { url } } })` |
| v6 | ✅ 支援 | `new PrismaClient()`（url 從 env 讀取）|
| v7 | ❌ 已廢除 | 需 `prisma.config.ts` + Driver Adapter |

---

### 錯誤 4：`invalid port number in database URL`

**錯誤訊息：**
```
Invalid prisma.visitor.update() invocation:
The provided database string is invalid.
Error parsing connection string: invalid port number in database URL.
```

**根本原因 A（shell 特殊字元截斷）：**
舊的 `update-function-configuration` 指令直接把 URL 嵌入 shell：
```bash
--environment "Variables={DATABASE_URL=postgresql://...?sslmode=require&channel_binding=require}"
```
`&` 在 bash 中是「背景執行」符號，導致 `channel_binding=require"` 被當成背景指令，URL 在 `&` 處被截斷。

**根本原因 B（URL 中的 `@` 被錯誤 URL 編碼）：**
GitHub Secret 中的 `DATABASE_URL` 被存為：
```
postgresql://DB_USER:DB_PASSWORD%40DB_HOST...
```
`%40` 是 `@` 的 URL 編碼。但這個 `@` 是 PostgreSQL URL 的**結構分隔符**（分隔密碼和主機名），不應被編碼。Prisma 看到 `%40` 後把它當成密碼的一部分，整個主機名就消失了，URL 解析完全失敗。

**正確的 URL 格式：**
```
postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
           ^   ^         ^ ^
           |   |         | |-- 主機名（不應被編碼）
           |   |         |---- @ 是結構分隔符
           |   |-------------- 密碼（若密碼本身含@則需編碼為%40）
           |------------------ 使用者名稱
```

**修正 A：** 使用 `jq` 將 URL 安全序列化為 JSON：
```bash
jq -n --arg url "$DATABASE_URL" \
  '{"Variables":{"DATABASE_URL":$url}}' > /tmp/lambda-env.json
aws lambda update-function-configuration \
  --function-name $LAMBDA_FUNCTION_NAME \
  --environment file:///tmp/lambda-env.json
```

**修正 B：** 更新 GitHub Secret `DATABASE_URL`，移除 `%40` 改回 `@`，並移除 Prisma 不支援的 `&channel_binding=require` 參數。

---

### 錯誤 5：`AccessDeniedException lambda:GetFunctionConfiguration`

**錯誤訊息：**
```
User: arn:aws:iam::...:user/GitHub-Actions-S3-Deploy is not authorized
to perform: lambda:GetFunctionConfiguration
```

**根本原因：** `aws lambda wait function-updated` 指令內部會呼叫 `GetFunctionConfiguration` 來輪詢狀態，但 IAM 使用者只有 `UpdateFunctionCode` 與 `UpdateFunctionConfiguration` 權限，沒有 `GetFunctionConfiguration`。

**修正選項：**
| 方案 | 說明 | 選擇 |
| :--- | :--- | :--- |
| 加 IAM 權限 | 新增 `lambda:GetFunctionConfiguration` | 增加攻擊面，不選 |
| 改用 sleep | `sleep 15` 代替 wait | ✅ 採用（最小權限原則） |

---

### 錯誤 6：NeonDB 初始資料缺失

**錯誤訊息：**
```
Invalid prisma.visitor.update() invocation:
An operation failed because it depends on one or more records that were required but not found.
```

**根本原因：** Prisma 的 `update()` 操作要求目標紀錄必須已存在。NeonDB 資料表建立後沒有任何資料，`WHERE id = 1` 找不到記錄，操作失敗。

**修正：** 在 NeonDB SQL Editor 執行初始化：
```sql
CREATE TABLE IF NOT EXISTS "Visitor" (
  id    INTEGER PRIMARY KEY DEFAULT 1,
  count INTEGER NOT NULL DEFAULT 0
);
INSERT INTO "Visitor" (id, count) VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;
```

---

## 架構全貌（v2）

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
    ↓ [IAM Least Privilege + DATABASE_URL via Secrets]
NeonDB（Serverless PostgreSQL：Visitor table）
```

## 防禦層次總覽（v2 更新）

| 層次 | 技術 | 防禦目標 |
| :--- | :--- | :--- |
| DNS 層 | Cloudflare Proxy | 隱藏真實 IP，防止直連攻擊 |
| 邊緣層 | WAF + Bot Fight Mode | 攔截惡意掃描與爬蟲（降低 70%+） |
| 網路層 | S3 Bucket Policy IP 白名單 | 強制流量必須經過 Cloudflare |
| API 層 | API Gateway Throttling | 防止資源耗盡攻擊（429） |
| 應用層 | CORS 限制 + OPTIONS 預檢 | 防止跨站偽造請求 |
| 資料層 | IAM Least Privilege | 最小化資料洩漏爆炸半徑 |
| 金鑰層 | GitHub Secrets + jq 序列化 | 防止 DATABASE_URL 被 shell 截斷或洩漏 |
| 財務層 | AWS Budgets $0.01 警報 | 異常帳單即時通知 |

---

# v3 升級：Amazon Lex v2 Chatbot 整合

> 本章記錄在現有 v2 架構基礎上，新增 Amazon Lex v2 智慧 Chatbot 的完整實作流程。

---

## 新增服務說明

| 服務 | 角色 | 設定重點 |
| :--- | :--- | :--- |
| **Amazon Lex v2** | 自然語言理解（NLU）引擎 | Bot: ResumeBot, Language: en_US, Bot ID: F7MS13BUCP |
| **chatbot-fulfillment** | Lex Fulfillment Lambda | Python 3.12, arm64；處理 8 個 Intent + 多輪對話 Slot 邏輯 |
| **chatbot-proxy** | API Gateway → Lex 代理 Lambda | Python 3.12, arm64；呼叫 lexv2-runtime RecognizeText API |
| **API Gateway /chat** | 新增路由 | POST /chat → chatbot-proxy；與既有 /{proxy+} 共存 |

---

## Lex v2 Bot 設計

### Intent 設計（v3 擴充版）

| Intent | 觸發語句範例 | Slot | 處理方式 |
| :--- | :--- | :--- | :--- |
| `GetVisitorCount` | how many visitors, visitor count | 無 | Lambda 呼叫 GET /visitor API |
| `AskAboutMe` | who are you, about the owner | 無 | Lambda 回傳靜態個人介紹 |
| `AskSkills` | what skills, what tech stack | `skillType` | 多輪：Bot 反問類別，Lambda 回傳對應技能 |
| `AskProjects` | what projects, show me your work | `projectType` | 多輪：Bot 反問哪個專案，Lambda 回傳詳細介紹 |
| `AskEducation` | where did you study, education | `educationType` | 多輪：Bot 反問大學/高中，Lambda 回傳學歷 |
| `AskExperience` | what is your experience, teaching | `experienceType` | 多輪：Bot 反問類別，Lambda 回傳經歷 |
| `AskContact` | how can I contact you, email | 無 | Lambda 回傳聯絡資訊 |
| `AskAchievements` | what awards, certificates | `achievementType` | 多輪：Bot 反問類別，Lambda 回傳成就 |
| `FallbackIntent` | 其他輸入 | 無 | Lex 內建引導訊息 |

### Slot Type 設計

| Slot Type | 值 | 同義詞（節錄） |
| :--- | :--- | :--- |
| `SkillType` | programming, cloud, spoken | coding / aws / language |
| `ProjectType` | resume, cryptography | serverless / crypto / ttu |
| `EducationType` | university, high school | tatung / yilan |
| `ExperienceType` | teaching, activities, part-time | ta / events / job |
| `AchievementType` | awards, certificates, events | pupc / gemini / cybersec |

### 多輪對話架構（Dialog Code Hook）

所有含 Slot 的 Intent 均啟用 **Dialog Code Hook**，Lambda 在每一輪對話都被呼叫：

```
使用者輸入 → Lex v2 NLU → 識別 Intent → 呼叫 chatbot-fulfillment（dialog hook）
                                              │
                              Slot 未填入 → 回傳 Delegate → Lex 自動問提示語
                              Slot 已填入 → 回傳 Close + 對應回應字串
```

**Delegate 回傳範例（Slot 未填入時）：**
```python
return {
    "sessionState": {
        "dialogAction": {"type": "Delegate"},
        "intent": event["sessionState"]["intent"]
    }
}
```

**對話範例：**
```
User: what skills do you have
Bot:  Which type of skills? (programming / cloud / spoken languages)
User: cloud
Bot:  Cloud & DevOps skills: AWS S3, Lambda, API Gateway, DynamoDB...
```

### Lambda Fulfillment 架構

```
使用者輸入 → Lex v2 NLU → 識別 Intent → 觸發 chatbot-fulfillment Lambda
                                              │
                     GetVisitorCount  → GET /visitor API → 取得訪客數
                     AskAboutMe       → 回傳靜態個人介紹
                     AskContact       → 回傳聯絡資訊
                     AskSkills        → 讀取 skillType slot → 回傳對應技能
                     AskProjects      → 讀取 projectType slot → 回傳專案詳情
                     AskEducation     → 讀取 educationType slot → 回傳學歷
                     AskExperience    → 讀取 experienceType slot → 回傳經歷
                     AskAchievements  → 讀取 achievementType slot → 回傳成就
```

---

## chatbot-proxy 架構

```python
# backend/chatbot_proxy.py
lex.recognize_text(
    botId="F7MS13BUCP",
    botAliasId="TSTALIASID",
    localeId="en_US",
    sessionId=session_id,
    text=user_message
)
```

**為什麼需要 chatbot-proxy？**

瀏覽器 JavaScript 無法直接呼叫 Lex v2 Runtime API（需要 AWS 簽名 v4），必須透過後端 Lambda 代理，由 Lambda 的 IAM 角色持有 `lex:RecognizeText` 權限。

---

## IAM 設計（最小權限）

`chatbot-proxy` 執行角色僅授予對特定 Bot Alias 的 RecognizeText 權限：

```json
{
  "Effect": "Allow",
  "Action": "lex:RecognizeText",
  "Resource": "arn:aws:lex:us-east-1:933613018788:bot-alias/F7MS13BUCP/TSTALIASID"
}
```

---

## 架構全貌（v3）

```
使用者瀏覽器 (HTTPS)
      │
      ▼
Cloudflare CDN（WAF + Bot Fight Mode）
      │
      ▼
AWS S3（靜態網站：HTML / CSS / JS）
      │
      ├─── fetch POST /prod/visitor ──────► API Gateway
      │                                          │
      │                                    Lambda（訪客計數, Node.js 22）
      │                                          │
      │                                    NeonDB PostgreSQL
      │
      └─── fetch POST /chat ───────────────► API Gateway ($default stage)
                                                 │
                                           chatbot-proxy Lambda（Python）
                                                 │
                                           Amazon Lex v2（ResumeBot, en_US）
                                                 │
                                           chatbot-fulfillment Lambda（Python）
                                                 │
                                           回傳回應 → 前端對話框顯示
```

---

## v3 除錯記錄

### 錯誤 1：前端顯示 `undefined`（chatbot-proxy 從未被呼叫）

**現象：** 輸入任何問題，Bot 回應 `undefined`。CloudWatch 日誌群組 `/aws/lambda/chatbot-proxy` 不存在（Lambda 從未被呼叫）。

**根本原因：** API Gateway 路由衝突。

| 路由 | 類型 | 實際 URL |
| :--- | :--- | :--- |
| `/{proxy+} ANY` | catch-all | 匹配一切路徑，包含 `/prod/chat` |
| `POST /chat` | 明確路由 | 只匹配 `/chat`（不含 stage 前綴） |

前端使用 `/prod/chat`，被 `/{proxy+}` 攔截，請求轉發至**訪客計數 Lambda**，回傳 `{"count": X}`，導致 `data.reply` 為 undefined。

**修正：** 將前端 CHAT_API 從 `/prod/chat` 改為 `/chat`（$default stage 無 stage 前綴）：

```javascript
// ❌ 錯誤
const CHAT_API = 'https://3ai7u70ypd.execute-api.us-east-1.amazonaws.com/prod/chat';

// ✅ 正確（$default stage，路由為 /chat）
const CHAT_API = 'https://3ai7u70ypd.execute-api.us-east-1.amazonaws.com/chat';
```

**學習點：** HTTP API Gateway 的 `$default` stage 不在 URL 中加 stage 前綴。新增路由時須確認 stage 對應的 URL 格式。`/{proxy+}` catch-all 優先匹配所有未明確命中的路徑，容易遮蔽新路由。

---

### 錯誤 2：cloudflare-purge-action SHA 不存在

**現象：** GitHub Actions 失敗：`Unable to resolve action @a379f7c, unable to find version`

**根本原因：** 安全加固時填入的 commit SHA `a379f7cfab34e0f287c72c91f8e84a55e4b12e5` 並不存在於 `jakejarvis/cloudflare-purge-action` repo。

**修正：** 查詢正確 SHA：`git ls-remote https://github.com/jakejarvis/cloudflare-purge-action.git`，改為 `eee6dba0236093358f25bb1581bd615dc8b3d8e3`（v0.3.0 最新版）。

---

### 錯誤 3：Chatbot 查詢訪客數時計數遞增

**現象：** 每次在 chatbot 輸入「How many visitors?」，訪客計數就 +1。

**根本原因：** `chatbot-fulfillment` Lambda 呼叫 `POST /visitor`，而 POST 的邏輯是「先遞增再回傳」，導致每次查詢都被當成一次真實訪客。

**修正：**

1. `backend/index.mjs` 新增 GET 路由，只讀不遞增：
```javascript
// GET：只讀取，不遞增
if (method === 'GET') {
  const visitor = await prisma.visitor.findUnique({ where: { id: 1 } });
  return { ..., body: JSON.stringify({ count: visitor.count }) };
}
// POST：遞增計數（頁面載入時觸發）
const updatedVisitor = await prisma.visitor.update({ ..., data: { count: { increment: 1 } } });
```

2. `backend/chatbot_fulfillment.py` 改用 GET：
```python
# ❌ 舊
req = urllib.request.Request(VISITOR_API_URL, method="POST", headers={"Content-Type": "application/json"})
# ✅ 新
req = urllib.request.Request(VISITOR_API_URL, method="GET")
```

**最終 API 語意：**

| Method | 用途 | 計數變化 |
| :--- | :--- | :--- |
| `POST /visitor` | 頁面載入，記錄真實訪客 | +1 |
| `GET /visitor` | Chatbot 查詢現有計數 | 不變 |

---

### 錯誤 4：新增 Intent 全部顯示「Loading...」

**現象：** 擴充 6 個新 Intent（AskSkills, AskProjects 等）後，在 chatbot 測試時所有新 Intent 都只顯示「Loading...」，不呈現實際回應。

**根本原因：** 新建立的 Intent 沒有啟用 Lambda Code Hook。Lex v2 的運作邏輯如下：

| Intent 設定 | Lex 行為 |
| :--- | :--- |
| 未勾選 Code Hook | 直接使用 Closing Response 文字（即「Loading...」） |
| 勾選 Code Hook（Dialog / Fulfillment） | 呼叫 Alias 層級設定的 Lambda |

原有的 GetVisitorCount / AskAboutMe 有設定 Code Hook，Lambda 能被呼叫。新建立的 6 個 Intent 沒有勾選，Lex 直接回傳 Closing Response 的預留文字。

**修正：** 對每個新 Intent → 頁面最下方 **「程式碼掛接 - 選用」** → 勾選「使用 Lambda 函數進行初始化和驗證」→ 儲存意圖 → 重新 Build。

**學習點：** Lex v2 的 Lambda 連接是「Alias 層級設定函數 + Intent 層級勾選啟用」兩層才能觸發，缺一不可。只設定 Alias Lambda 但 Intent 未勾選，Lambda 不會被呼叫。

---

### 錯誤 5：多輪對話 Slot 無限循環（Loop）

**現象：** 在多輪對話中，使用者輸入有效的 Slot 值（如 `events`、`certificate`）後，Bot 不斷重複問同一個問題，無法進入下一步。

**根本原因 A：NLU 衝突（`events` 同時存在多個 Slot Type）**

`events` 同時是 `AchievementType` 的值，也是 `ExperienceType` 的同義詞（activities 的同義詞）。當使用者在填入 `achievementType` Slot 時輸入「events」，Lex NLU 可能將其解析為觸發 `AskExperience` Intent，而非填入當前 Slot，導致對話狀態重置。

**根本原因 B：單複數形式不匹配（`certificate` vs `certificates`）**

Slot Type 定義的值為 `certificates`（複數），但使用者輸入 `certificate`（單數）。Slot resolution 設定為「限制為位置值」時，無法匹配，Slot 始終為空，Bot 持續詢問。

**根本原因 C：Lambda 未處理 else 情境導致無限 Delegate**

```python
# ❌ 有問題的邏輯
if ach_type == "awards":   return close(...)
elif ach_type == "certificates": return close(...)
elif ach_type == "events": return close(...)
# 若 Slot 有值但不匹配以上任一條件 → 落入 delegate(event)
# → Lex 再次詢問 → 使用者再次輸入 → 再次 delegate → 無限循環
return delegate(event)
```

**修正 A：Lex Console 補充同義詞**

在 `AchievementType` Slot Type 新增：
- `certificates` → 新增同義詞：`certificate`
- `events` → 新增同義詞：`event`、`conference`

**修正 B：Lambda 加 else 兜底，破除循環**

```python
# ✅ 正確做法：Slot 已填入但不匹配任何分支時，回傳完整摘要而非 delegate
if ach_slot and ach_slot.get("value"):
    ach_type = ach_slot["value"]["interpretedValue"].lower()
    if ach_type == "awards":
        return close(event, "Awards: PUPC 2024 Bronze Award.")
    elif ach_type in ("certificates", "certificate"):
        return close(event, "Certifications: ...")
    elif ach_type in ("events", "event"):
        return close(event, "Notable events: ...")
    else:
        # Slot 有值但未命中任何分支 → 回傳完整摘要，防止無限循環
        return close(event, "Achievements summary: ...")
return delegate(event)  # 只有 Slot 為空時才 delegate
```

**修正 C：Lambda 對 Slot 值加入多形式比對**

```python
# 同時處理單複數、連字符等變體
elif exp_type in ("part-time", "part time", "job", "work"):
    return close(event, "Part-time work: ...")
```

**學習點：**
- Slot 值設計應包含使用者可能輸入的所有形式（單複數、縮寫、同義詞）
- Lambda 必須為 Slot 已填入但不匹配任何分支的情況設置 `else` fallback，避免 `delegate` 造成循環
- 不同 Slot Type 之間的同義詞應盡量避免重疊，否則 NLU 在 Slot 填入階段容易混淆

---

### 錯誤 6：Slot 回答被 Lex 路由至 FallbackIntent，對話上下文遺失

**現象：** Bot 問「Which type of skills? (programming / cloud / spoken languages)」後，使用者輸入 `cloud`、`teaching`、`awards` 等正確答案，Bot 卻回應「Sorry, I didn't understand. You can ask me: - How many visitors?...」，且問題無法繼續。

**根本原因：Lex NLU 在 Slot 填充階段將使用者答案錯誤路由至 FallbackIntent**

當 Bot 處於 Slot 填充狀態，使用者下一句話有兩種可能：
1. Lex 成功辨識為 Slot 值 → 填入 Slot → 呼叫 Lambda → 回傳答案 ✅
2. Lex 無法辨識為 Slot 值 → 觸發 **FallbackIntent** → 顯示 FallbackIntent 的 Closing Response ❌

觸發路由 2 的原因：部分 Slot 值（如 `cloud`、`teaching`、`awards`）與其他 Intent 的 Utterances 語意重疊，或 NLU 信心度不足，導致 Lex 放棄 Slot 填充並改觸發 FallbackIntent。

**為什麼部分值成功、部分值失敗？**

| 成功（Lex 識別為 Slot 值）| 失敗（被路由至 FallbackIntent）|
| :--- | :--- |
| programming, spoken languages | cloud（與 AskSkills utterance 重疊）|
| activities, university, high school | teaching（與 AskExperience utterance 重疊）|
| cryptography system | awards, certificates（與 AskAchievements utterance 重疊）|

**FallbackIntent 沒有 Code Hook → 上下文完全遺失**

FallbackIntent 觸發後，因為 Code Hook 未啟用，Lex 直接顯示 FallbackIntent 的靜態 Closing Response 文字，Lambda 完全未被呼叫，之前的對話狀態（正在詢問哪個 Slot）也隨之消失。

**修正：Session Attributes + FallbackIntent Code Hook 雙管齊下**

**修正 A：每次詢問 Slot 時，在 Session Attributes 記錄 `pending` 狀態**

```python
def ask_pending(event, slot_name, topic, message):
    attrs = {**_session_attrs(event), "pending": topic}  # 記錄 pending 話題
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": event["sessionState"]["intent"],
            "sessionAttributes": attrs   # 跨 Intent 保留，FallbackIntent 也能讀到
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }
```

**為什麼 Session Attributes 能跨 Intent 存活？**
Lex v2 的 Session Attributes 屬於 Session 層級，不屬於特定 Intent。即使 FallbackIntent 被觸發，Session Attributes 仍保留上一輪設定的值。

**修正 B：啟用 FallbackIntent Code Hook，Lambda 接管 FallbackIntent**

Lex Console → FallbackIntent → 程式碼掛接 → 勾選「使用 Lambda 函數進行初始化和驗證」→ 儲存 → Build

**修正 C：Lambda 新增 FallbackIntent Handler，讀取 `pending` 恢復上下文**

```python
def handle_fallback(event):
    pending = _session_attrs(event).get("pending", "")
    t = _transcript(event)          # 讀取使用者原始輸入

    if pending == "skills":
        return respond(event, _skills_text(_match_skill(t) or "all"))
    if pending == "experience":
        return respond(event, _experience_text(_match_experience(t) or "all"))
    # ... 其他 pending 狀態 ...

    return respond(event, "Sorry, I didn't understand. Try: skills, projects, education...")
```

**修正 D：使用 `inputTranscript` 直接比對關鍵字，不依賴 Lex Slot 填充**

```python
def _match_experience(t):
    if any(w in t for w in ["teaching", "ta", "teacher", "lab", "assistant"]):
        return "teaching"
    if any(w in t for w in ["activities", "activity", "coordinator", "organizer"]):
        return "activities"
    if any(w in t for w in ["part", "job", "work", "part-time"]):
        return "part-time"
    return None
```

**完整對話流程（修正後）：**

```
使用者: "What experience?"
Lambda: AskExperience → transcript 無法比對 → ask_pending() 設 pending="experience"
Bot回應: "Which experience? (teaching / activities / part-time)"

使用者: "teaching"
Lex NLU: 無法匹配 → 觸發 FallbackIntent
Lambda: handle_fallback() → pending="experience" → _match_experience("teaching") = "teaching"
Bot回應: "Teaching experience: Programming Learning Center TA..."  ✅
```

**學習點：**
- Lex 的 Slot 填充和 Intent 辨識是同一個 NLU pipeline，語意重疊的詞彙可能被誤判為 Intent 而非 Slot 值
- Session Attributes 是解決跨 Intent 狀態傳遞的標準做法
- FallbackIntent Code Hook 是多輪對話的最後防線，必須啟用才能處理 NLU 辨識失敗的情況
- `inputTranscript` 直接讀取使用者原始輸入，比依賴 Lex Slot 填充更可靠

---

<a id="local-env"></a>

# 本機開發環境建置與 Prisma 7 本地探索記錄

> 本章記錄本機 Windows 開發環境的建置過程，以及在本地嘗試使用 Prisma 7 時所遭遇的一系列錯誤與解決方法。

---

## 環境建置

### yarn 安裝

原本嘗試使用 `npx` 執行 Prisma 相關指令，但在 Windows 環境下持續出現 `command not found` 或無法正確解析路徑的問題。

**根本原因：** Windows 的 PATH 環境變數設定、PowerShell 執行政策，以及 `npx` 依賴 npm 全域快取的方式，在某些 Windows 環境配置下會造成指令無法正確找到可執行檔。

**解決方案：** 從 [yarnpkg.com](https://yarnpkg.com) 下載 `.msi` 安裝檔直接安裝，確保 yarn 被正確加入 PATH：

```
yarn --version
→ 1.22.22
```

`yarn` 相比 `npx` 的優點：
- 所有指令透過 `yarn prisma ...` 執行，確保使用的是**專案本地**安裝的版本而非全域版本
- lockfile（`yarn.lock`）鎖定依賴樹，避免版本漂移
- 在 CI/CD 環境（GitHub Actions）中行為一致可預期

---

## Prisma 7 本地探索過程

### 步驟與錯誤時間軸

#### 步驟 1：安裝 Prisma CLI

```bash
yarn add prisma --dev
```

成功安裝 `prisma@7.6.0`（85 個依賴），但此時尚未安裝 `@prisma/client`。

---

#### 步驟 2：初始化 Prisma

```bash
yarn prisma init
```

Prisma 7 的 `init` 會自動產生三個檔案：

| 檔案 | 用途 |
| :--- | :--- |
| `prisma/schema.prisma` | 資料模型定義 |
| `prisma.config.ts` | Prisma 7 新增：CLI 工具的連線設定（migrate / studio 用） |
| `.env` | 環境變數範本 |

> **與 Prisma 6 的差異：** Prisma 6 只產生 `schema.prisma` 和 `.env`；Prisma 7 額外產生 `prisma.config.ts`，這是 Prisma 7 架構重大變化的體現。

---

#### 步驟 3：`yarn prisma db push` 失敗（兩次）

**錯誤訊息：**
```
Error: Prisma schema validation - (get-config wasm)
Error code: P1012
error: The datasource property `url` is no longer supported in schema files.
Move connection URLs for Migrate to `prisma.config.ts`
--> prisma\schema.prisma:8
  7 | provider = "postgresql"
  8 | url      = env("DATABASE_URL")
Prisma CLI Version : 7.6.0
```

**根本原因：** `schema.prisma` 中的 `url = env("DATABASE_URL")` 在 Prisma 7 已被廢除。連線字串需移至 `prisma.config.ts`。

**處置：** 先安裝 `@types/node`（TypeScript 環境依賴）後，將 `DATABASE_URL` 設定移至 `prisma.config.ts`，第三次 `db push` 成功：
```
Datasource "db": PostgreSQL database "neondb", schema "public"
at "[your-neondb-pooler-endpoint].neon.tech"

Your database is now in sync with your Prisma schema. Done in 8.06s
```

---

#### 步驟 4：`yarn prisma generate` 失敗 — 找不到 Client

**錯誤訊息：**
```
Error: Could not resolve @prisma/client.
Please try to install it with yarn install @prisma/client and rerun npx "prisma generate"
```

**根本原因：** 只安裝了 `prisma`（CLI 工具），沒有安裝 `@prisma/client`（runtime 套件）。這兩個套件是分開的：

| 套件 | 類別 | 用途 |
| :--- | :--- | :--- |
| `prisma` | devDependency | CLI 工具（generate / migrate / studio） |
| `@prisma/client` | dependency | Runtime：在程式碼中 `import { PrismaClient }` |

---

#### 步驟 5：安裝 `@prisma/config` 後版本衝突

執行 `yarn add @prisma/config -D`，yarn 自動安裝了 `@prisma/client@6.19.2`（最新的穩定版），但 CLI 是 `prisma@7.6.0`。

**錯誤訊息：**
```
Cannot find module 'D:\user\Desktop\learn\node_modules\@prisma\client\runtime\
query_compiler_fast_bg.postgresql.wasm-base64.js'
```

**根本原因：** Prisma CLI（v7）嘗試使用 v7 的 WASM 查詢引擎，但 `@prisma/client`（v6）的 runtime 目錄不包含此 WASM 檔案，兩者無法搭配。

| 版本組合 | 結果 |
| :--- | :--- |
| CLI v7 + Client v6 | ❌ WASM 模組找不到 |
| CLI v6 + Client v6 | ✅ 相容 |
| CLI v7 + Client v7 | ✅ 相容 |

---

#### 步驟 6：統一版本至 v7.6.0，generate 成功

```bash
yarn add prisma@7.6.0 @prisma/client@7.6.0 @prisma/config@7.6.0 -D
```

```
✔ Generated Prisma Client (v7.6.0) to .\node_modules\@prisma\client in 647ms
```

---

#### 步驟 7：清空 node_modules 重新安裝，驗證乾淨環境

```powershell
Remove-Item -Recurse -Force node_modules
yarn install
```

`postinstall` hook 自動執行 `prisma generate`，確認從乾淨狀態也能成功產生。

---

## npx 與 Prisma 執行錯誤完整彙整

以下彙整在本地與 CI/CD 環境中遭遇的 `npx` 及 Prisma generate/deploy 問題：

### 錯誤 A：`npx prisma` 在 Windows 環境下無法執行

**現象：** `npx prisma generate` 出現 `command not found` 或 PowerShell 路徑解析失敗。

**原因：** Windows PATH 設定、PowerShell 執行政策，以及 npx 依賴 npm 全域快取，在某些環境配置下無法正確找到本地安裝的二進位檔。

**解決：** 改用 `yarn prisma generate`，確保使用專案 `node_modules/.bin` 內的本地版本。

---

### 錯誤 B：引擎架構不匹配（Binary Target Mismatch）

**現象（Lambda 執行時）：**
```
PrismaClientInitializationError: Query engine binary for current platform
"linux-arm64-openssl-3.0.x" could not be found.
```

**原因：** `prisma generate` 預設根據「當前執行環境」（GitHub Actions Ubuntu x64 或 Windows x64）下載引擎，但 Lambda 執行在 **arm64** 架構。

**解決：** 在 `schema.prisma` 明確宣告兩個目標：
```prisma
binaryTargets = ["native", "linux-arm64-openssl-3.0.x"]
```
- `native`：本機開發用（Windows/macOS/Ubuntu x64）
- `linux-arm64-openssl-3.0.x`：Lambda Graviton2 用

---

### 錯誤 C：舊版引擎快取污染（Stale Engine Cache）

**現象：** 明明更新了程式碼，Lambda 依然回傳舊版本的錯誤（如 `Unknown property`）。

**原因：** GitHub Actions 工作目錄或 `node_modules/.prisma` 殘留舊版 Client 檔案，新的 generate 沒有完整覆蓋。

**解決：**
```bash
rm -rf node_modules/.prisma
yarn prisma generate
```

---

### 錯誤 D：Prisma Client 建構子屬性錯誤

**現象：**
```
Unknown property datasourceUrl provided to PrismaClient constructor
Unknown property datasources provided to PrismaClient constructor
```

**原因：** CLI 版本與 Client 版本不一致，或使用了錯誤版本的語法。

| 屬性 | Prisma 版本 | 狀態 |
| :--- | :--- | :--- |
| `datasources: { db: { url } }` | v4 / v5 | 已廢除 |
| `datasourceUrl: "..."` | v7（新語法） | 僅 v7 支援 |
| `new PrismaClient()` | v6（URL 從 env 讀取）| ✅ 推薦 |

**解決：** 統一 `prisma` CLI 與 `@prisma/client` 版本（本專案 Lambda 使用 **v6.6.0**）。

---

### 錯誤 E：打包體積超過 Lambda 限制

**現象：**
```
RequestEntityTooLargeException
```

**原因：** Prisma 引擎包含多平台的 `.node` 二進位檔，全部打包後超過 Lambda API 直傳 50MB 上限。

**解決：**
1. 打包前刪除非 arm64 引擎：
   ```bash
   find node_modules -name "*.node" ! -name "*linux-arm64*" -delete
   ```
2. 移除開發用套件（`@prisma/engines`、`prisma` CLI 本身）
3. 透過 S3 中轉上傳（最大 250MB）

---

## Prisma 部署最佳實踐總結（本地 + CI/CD）

```
1. 清理環境
   rm -rf node_modules/.prisma
   ↓
2. 精確安裝
   yarn install --ignore-engines
   ↓
3. 指定目標產生引擎
   binaryTargets = ["native", "linux-arm64-openssl-3.0.x"]
   yarn prisma generate
   ↓
4. 精簡打包
   刪除 x64 引擎 + 開發工具 → zip
   ↓
5. S3 中轉部署
   aws s3 cp → aws lambda update-function-code --s3-bucket
   ↓
6. 安全注入環境變數
   jq 序列化 DATABASE_URL → aws lambda update-function-configuration
```
