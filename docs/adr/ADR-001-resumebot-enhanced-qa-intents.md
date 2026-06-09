---
status: Draft
date: 2026-05-27
---

# ADR-001：擴充 ResumeBot Q&A Intent 集，涵蓋履歷全內容

## Status

**Draft** — 待人類審核後改為 Accepted。實作必須等此 ADR 被 Accept。

## Context

現有 ResumeBot 僅有 2 個功能性 Intent（GetVisitorCount、AskAboutMe），回答範圍極窄。
訪客在 saibusu.com 開啟 chatbot 後，無法透過對話了解：
- 李軒杰的技能與技術棧
- 學歷與學業成績
- 參與的專案
- 在學經歷（助教、活動）
- 聯絡資訊
- 得獎與證照

目前 FallbackIntent 幾乎接收所有問題，使 chatbot 實用性極低。
目標是讓 ResumeBot 能完整回答履歷網站上所有可公開資訊。

## Decision

在現有 Lex v2 ResumeBot（en_US）新增 6 個 Intent，並在 `chatbot-fulfillment` Lambda 對應處理。

所有新 Intent 皆使用**靜態回應**（hardcoded string in Lambda），不新增任何 API 呼叫或資料庫存取。

### 新增 Intent 一覽

| Intent | 代表問題 | 回應來源 |
| :--- | :--- | :--- |
| `AskSkills` | what skills / what tech stack | Lambda 靜態字串 |
| `AskProjects` | what projects / tell me about your work | Lambda 靜態字串 |
| `AskEducation` | where did you study / education | Lambda 靜態字串 |
| `AskExperience` | teaching experience / activities | Lambda 靜態字串 |
| `AskContact` | how to contact / email / github | Lambda 靜態字串 |
| `AskAchievements` | awards / certificates / achievements | Lambda 靜態字串 |

### 變更範圍

1. **Lex Console（手動）**：新增 6 個 Intent + Sample utterances + Closing response → Build
2. **`backend/chatbot_fulfillment.py`**：新增 6 個 `elif` 分支
3. **`frontend/index.html`**：更新 welcome 訊息，提示使用者可問的問題範圍

## Consequences

**接受的 trade-off：**
- 回應為靜態字串，履歷更新時需同步更新 Lambda 程式碼（手動維護）
- Lex 仍然需要每次修改 Intent 後手動 Build（非 CI/CD 自動化）

**引入的風險：**
- Intent 數量增加後，Lex NLU 可能出現意圖混淆（特別是相似問題）
- 需要為每個 Intent 提供至少 3 條 utterances 才能正確觸發

**後續工作：**
- 部署後需對每個新 Intent 測試至少 3 種問法
- 若某 Intent 觸發率過低，可補充 utterances

## Alternatives Considered

### 方案 A：使用 Amazon Kendra 或 Knowledge Base（RAG）
- 優點：自動從網頁抓取內容，維護成本低
- 缺點：Kendra 最低費用 $810/月，不符合個人專案零成本目標；設定複雜度高

### 方案 B：在前端 JavaScript 直接 hardcode Q&A（不透過 Lex）
- 優點：零 AWS 費用，部署簡單
- 缺點：失去 Lex NLU 自然語言理解能力，關鍵字比對脆弱，無法處理同義問法
- 棄選原因：期末專案需展示 AWS Lex 整合深度
