# 李軒杰 — 雲端履歷網站

個人履歷靜態網站，部署於 AWS，整合 Lambda 訪客計數器。

## 專案亮點

**技術棧：AWS (S3, Lambda, API Gateway, DynamoDB), Cloudflare WAF, Python**

- **深層防禦實作 (Defense in Depth)**：建構多層防禦體系，包含 Cloudflare WAF 規則攔截惡意掃描、S3 Bucket Policy 實施來源 IP 白名單（Origin Cloaking），以及 API Gateway 限流（Throttling）防止資源耗盡攻擊。
- **無伺服器架構優化**：利用 Lambda 搭配 DynamoDB 原子操作（Atomic Counter）開發高性能訪客計數器，有效避免併發請求下的 Race Condition 問題。
- **成本與效能管理**：透過 Cloudflare CDN 快取與 DNS 優化（移除冗餘 Route 53 託管），並開啟 Bot Fight Mode 降低 70% 以上無效流量，將維運成本降至近乎零支出。
- **最小權限原則 (Least Privilege)**：精確配置 IAM 執行角色政策，確保雲端資源間的授權僅限於必要操作，符合業界資安合規標準。

## 架構

```
使用者瀏覽器
    ↓
Cloudflare（DNS + CDN + 防護）
    ↓
AWS S3（靜態網站託管）
    ↓ (fetch API)
AWS API Gateway
    ↓
AWS Lambda（Python）
    ↓
AWS DynamoDB（訪客計數）
```

## 專案結構

```
├── frontend/
│   ├── index.html          # 主頁面（履歷 + 訪客計數器 UI）
│   └── photo.png           # 大頭貼
├── backend/
│   └── lambda_function.py  # Lambda 訪客計數邏輯
├── infrastructure/
│   ├── s3-bucket-policy.json     # S3 僅允許 Cloudflare IP 存取
│   └── iam-lambda-policy.json    # Lambda 執行角色 IAM Policy
└── README.md
```

## AWS 服務說明

| 服務 | 用途 |
| :--- | :--- |
| **S3** | 靜態網站檔案託管 |
| **Route 53** | 域名註冊（選用：目前由 Cloudflare DNS 代管，優化成本結構） |
| **Cloudflare** | CDN、DNS、DDoS 防護（WAF / Bot Fight Mode） |
| **ACM** | SSL/TLS 憑證 |
| **API Gateway** | HTTP API 端點與流量限流（Throttling） |
| **Lambda** | 無伺服器訪客計數後端（Python 3.12） |
| **DynamoDB** | 持久化訪客計數（原子操作） |

## 安全設計

- **API Gateway Throttling**：設定速率限制（Rate: 2）與高載限制（Burst: 5），從基礎設施層級防止 Lambda 與 DynamoDB 被惡意刷量攻擊，確保預算安全。
- **S3 Bucket Policy**：限制僅 Cloudflare 的 IP 段可存取，阻擋直接存取 S3 URL。
- **Lambda CORS**：設定僅允許 `https://saibusu.com` 跨域請求。
- **DynamoDB 原子操作**：使用 `ADD` 操作防止 Race Condition。

### Origin Cloaking（來源遮蔽）

我透過 Cloudflare 實作了 Origin Cloaking（來源遮蔽）。除了設定橘色雲朵隱藏後端節點，我更在 AWS S3 套用了僅允許 Cloudflare IP 區段的 Bucket Policy，確保所有流量都必須經過 Cloudflare WAF 過濾，徹底杜絕了繞過 CDN 攻擊原始伺服器的可能性。

```
攻擊者直接請求 S3 URL
    ↓
S3 Bucket Policy 比對來源 IP
    ↓ 非 Cloudflare IP → 403 Forbidden
    ↓ Cloudflare IP   → 正常回應
```

| 防護層 | 實作方式 |
|--------|---------|
| DNS 遮蔽 | Cloudflare Proxy（橘色雲朵），隱藏真實 S3 endpoint |
| IP 白名單 | S3 Bucket Policy 僅允許 15 個 Cloudflare IP 區段 |
| WAF 過濾 | 所有請求強制經過 Cloudflare WAF 才能到達 S3 |

### Cloudflare WAF 與 Bot 防護

在 CDN 層級，我實作了 Cloudflare WAF 自訂規則與 Bot Fight Mode，有效降低了 70% 以上的自動化掃描流量。透過定期分析 Security Events 日誌，我能主動監控並應對針對性攻擊，確保後端 Serverless 架構的穩定與成本安全。

| 防護機制 | 效果 |
| :--- | :--- |
| **WAF 自訂規則** | 攔截惡意請求模式與異常 User-Agent |
| **Bot Fight Mode** | 自動化掃描流量降低 70%+ |
| **API Throttling** | 設定 Rate: 2 / Burst: 5，阻斷 API 暴力請求，防止後端成本失控 |
| **Security Events 日誌** | 主動監控，快速識別針對性攻擊 |
| **成本安全** | 透過限流與機器人過濾，確保 AWS 帳單維持在免費額度內 |

## 部署步驟

1. 將 `frontend/` 內容上傳至 S3 Bucket
2. 套用 `infrastructure/s3-bucket-policy.json` 至 S3
3. 建立 DynamoDB Table：`ResumeVisitorCount`，Partition Key 為 `id`（String）
4. 部署 `backend/lambda_function.py` 至 Lambda（Runtime: Python 3.12）
5. 套用 `infrastructure/iam-lambda-policy.json` 至 Lambda 執行角色
6. 在 API Gateway 建立 GET route 並整合 Lambda
7. 更新 `iam-lambda-policy.json` 中的 `YOUR_REGION` 與 `YOUR_ACCOUNT_ID`
8. **基礎設施保護**：在 API Gateway **Protect → Throttling** 設定速率限制（Rate: 2, Burst: 5）
9. **財務防禦**：建立 **AWS Budgets** 預算警報（設定為 $0.01 USD），確保帳單異常時能立即收到通知
