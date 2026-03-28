# 李軒杰 — 雲端履歷網站

個人履歷靜態網站，部署於 AWS，整合 Lambda 訪客計數器。

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
|------|------|
| **S3** | 靜態網站檔案託管 |
| **Route 53** | 域名管理（saibusu.com） |
| **Cloudflare** | CDN、DNS、DDoS 防護 |
| **ACM** | SSL/TLS 憑證 |
| **API Gateway** | REST API 端點 |
| **Lambda** | 無伺服器訪客計數後端 |
| **DynamoDB** | 持久化訪客計數（原子操作） |

## 安全設計

- S3 Bucket Policy 限制僅 Cloudflare 的 IP 段可存取，阻擋直接存取 S3 URL
- Lambda CORS 設定僅允許 `https://saibusu.com` 跨域請求
- DynamoDB 使用原子操作（`ADD`）防止 Race Condition

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

## 部署步驟

1. 將 `frontend/` 內容上傳至 S3 Bucket
2. 套用 `infrastructure/s3-bucket-policy.json` 至 S3
3. 建立 DynamoDB Table：`ResumeVisitorCount`，Partition Key 為 `id`（String）
4. 部署 `backend/lambda_function.py` 至 Lambda（Runtime: Python 3.12）
5. 套用 `infrastructure/iam-lambda-policy.json` 至 Lambda 執行角色
6. 在 API Gateway 建立 GET route 並整合 Lambda
7. 更新 `iam-lambda-policy.json` 中的 `YOUR_REGION` 與 `YOUR_ACCOUNT_ID`
