# saibusu.com 雲端架構技術筆記

> 本筆記為 **saibusu.com** 雲端履歷專案的完整技術深度彙整，涵蓋 Serverless 架構實作與深層防禦（Defense in Depth）的完整流程解析。

---

## 目錄

1. [Amazon S3 靜態網站託管與來源遮蔽（Origin Cloaking）](#步驟一amazon-s3-靜態網站託管與來源遮蔽origin-cloaking)
2. [Cloudflare 邊緣計算層與多層防禦體系](#步驟二cloudflare-邊緣計算層與多層防禦體系)
3. [AWS API Gateway 流量控管與 Throttling 機制](#步驟三aws-api-gateway-流量控管與-throttling-機制)
4. [AWS Lambda 運算邏輯與 DynamoDB 原子操作](#步驟四aws-lambda-運算邏輯與-dynamodb-原子操作)
5. [GitHub Actions CI/CD 與自動化快取清除](#步驟五github-actions-cicd-與自動化快取清除)

---

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
