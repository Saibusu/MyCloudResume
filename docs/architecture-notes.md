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
