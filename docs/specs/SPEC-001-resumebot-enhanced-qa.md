---
title: ResumeBot Enhanced Q&A — 擴充履歷問答 Intent 集
related-adr: ADR-001
status: Draft
date: 2026-05-27
---

# SPEC-001：ResumeBot 擴充 Q&A Intent 集

## Goal

在現有 ResumeBot 基礎上新增 6 個 Intent，使 chatbot 能回答 saibusu.com 履歷網站上的所有公開資訊，讓訪客透過對話完整了解李軒杰的技能、學歷、專案、經歷、聯絡方式與成就。

## Inputs

| 來源 | 格式 | 說明 |
| :--- | :--- | :--- |
| 使用者文字輸入 | 英文自然語言 | 由 chatbot-proxy 轉發至 Lex v2 |
| Lex Intent 辨識結果 | `event["sessionState"]["intent"]["name"]` | chatbot-fulfillment 的路由依據 |

## Outputs

| 情境 | 輸出 |
| :--- | :--- |
| Intent 成功辨識 | `{"reply": "<對應靜態回應字串>"}` via chatbot-proxy |
| Intent 未辨識 | FallbackIntent → 引導訊息（現有行為，不變） |

### 各 Intent 回應內容

**AskSkills**
```
Tech stack: AWS (S3, Lambda, API Gateway, DynamoDB, Lex v2), Cloudflare WAF, Node.js, Python, Prisma ORM, NeonDB PostgreSQL, GitHub Actions CI/CD.
Languages: C, C++, PHP, Java, HTML/CSS/JavaScript, SQL.
```

**AskProjects**
```
1. Cloud Security Serverless Resume (this site) — AWS S3 + Lambda + API Gateway + Cloudflare WAF, Defense in Depth architecture. GitHub: github.com/Saibusu/MyCloudResume
2. Gamified Cryptography Learning System — Team leader, system architecture & backend. Live: crypto.ttu.taipei (2024-2025)
```

**AskEducation**
```
Tatung University — Computer Science & Engineering + Information Security Program.
High School: Yi-Lan Senior High School.
Class rank: 42nd (top 29.86%).
```

**AskExperience**
```
Teaching Assistant: Programming Learning Garden (2024), Programming Lab I & II (2026).
Events: TYPL Engineering Faculty Exchange coordinator, Media Design Department Design Week leader.
```

**AskContact**
```
Email: saibusu8888@gmail.com
GitHub: github.com/Saibusu
Website: saibusu.com
```

**AskAchievements**
```
Awards: PUPC 2024 Bronze Award.
Certificates: Gemini Certified Educator, AWS Cloud Security Serverless Architecture.
Events: CYBERSEC 2024 Taiwan Security Conference, Team Lab Creative Process Workshop, Taiwan-Japan Cultural Exchange Design.
```

## Side Effects

| 項目 | 說明 |
| :--- | :--- |
| Lex Console | 新增 6 個 Intent（手動），每個至少 4 條 utterances，需重新 Build |
| `chatbot-fulfillment` Lambda | 新增 6 個 `elif` 分支，需在 AWS Console Deploy |
| `frontend/index.html` | 更新 welcome 訊息，列出可詢問的主題 |
| GitHub repo | `backend/chatbot_fulfillment.py` 同步更新 |
| 無 DB 存取 | 所有回應為靜態字串，不觸碰 NeonDB |

## Edge Cases

| 情境 | 處理方式 |
| :--- | :--- |
| Lex 辨識信心度低，觸發 FallbackIntent | 現有 FallbackIntent 回傳引導訊息 |
| 兩個 Intent utterances 過於相似導致混淆 | utterances 設計時須明確區隔語意；測試後補充 |
| Lambda 新分支拋出例外 | 現有 try/catch 兜底，回傳「暫時無法回答」 |
| 使用者問中文 | Lex en_US 可能辨識失敗 → FallbackIntent 回傳提示改用英文 |

## Done When

以下條件**全部成立**時視為完成：

- [ ] Lex Console 中可看到 8 個 Intent（含原有 2 個 + FallbackIntent + 新增 6 個）
- [ ] 每個新 Intent 至少 4 條 utterances，Bot 已 Build 成功
- [ ] 在 Lex Test 面板輸入下列問題，各自觸發對應 Intent：
  - "what skills do you have" → AskSkills
  - "tell me about your projects" → AskProjects
  - "where did you study" → AskEducation
  - "what is your experience" → AskExperience
  - "how can I contact you" → AskContact
  - "what awards do you have" → AskAchievements
- [ ] saibusu.com chatbot 實測上述 6 個問題，皆回傳正確文字
- [x] 前端 welcome 訊息更新，提示新增的問答主題
- [x] `backend/chatbot_fulfillment.py` 已同步 commit 至 GitHub

## Rollback Plan

- **Lex**：刪除新增的 6 個 Intent → Build → 恢復原狀（TestBotAlias 不受影響）
- **Lambda**：AWS Console 貼回舊版 `chatbot_fulfillment.py` 程式碼 → Deploy
- **Frontend**：`git revert` welcome 訊息的 commit → push → GitHub Actions 自動部署
- 無 schema 變更，無需 DB rollback

## 實作步驟（ADR Accept 後執行）

### Step A：Lex Console（手動）
1. Lex → ResumeBot → 草稿版本 → English (US) → Intents
2. 依序建立 6 個 Intent（見下方 utterances 清單）
3. 各 Intent 填入 Closing response（暫用靜態文字；Lambda 會覆蓋）
4. 右上角 **Build**

### Intent Utterances 清單

**AskSkills**
```
what skills do you have
what is your tech stack
what programming languages do you know
what technologies do you use
what are your technical skills
```

**AskProjects**
```
what projects have you done
tell me about your projects
what have you built
show me your work
what is your portfolio
```

**AskEducation**
```
where did you study
what is your education
what school did you go to
tell me about your background
what is your degree
```

**AskExperience**
```
what is your experience
tell me about your work experience
what have you done
teaching experience
what activities were you involved in
```

**AskContact**
```
how can I contact you
what is your email
what is your github
how do I reach you
contact information
```

**AskAchievements**
```
what awards do you have
what certificates do you have
tell me your achievements
what competitions have you won
what are your accomplishments
```

### Step B：Lambda（AWS Console）
貼上更新後的 `chatbot_fulfillment.py`（新增 6 個 elif）→ Deploy

### Step C：Frontend
更新 `frontend/index.html` welcome 訊息 → git push → Actions 自動部署
