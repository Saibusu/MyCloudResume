import { PrismaClient } from '@prisma/client'
// 初始化 Prisma 客戶端
const prisma = new PrismaClient()

export const handler = async (event) => {
  try {
    // 1. 執行原子更新：將 id 為 1 的訪客計數加 1
    // 這能防止多位訪客同時進入時發生數據遺失 (Race Condition)
    const updatedVisitor = await prisma.visitor.update({
      where: { id: 1 },
      data: { count: { increment: 1 } },
    });

    // 2. 回傳成功的響應與跨網域 (CORS) 設定
    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "https://saibusu.com", // 確保只有你的網站能呼叫
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ count: updatedVisitor.count }),
    };
  } catch (error) {
    // 3. 錯誤處理：若資料庫連線失敗或找不到資料，回傳 500
    console.error('Database Error:', error);
    return {
      statusCode: 500,
      headers: {
        "Access-Control-Allow-Origin": "https://saibusu.com",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ error: "Failed to update visitor count" }),
    };
  }
};