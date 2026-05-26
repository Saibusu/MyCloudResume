import { PrismaClient } from '@prisma/client'

// Lazy singleton：在 handler 外宣告，在內初始化，利用 Lambda 執行環境重用
let prisma;

export const handler = async (event) => {

  const method = event.requestContext?.http?.method || event.httpMethod;

  // OPTIONS 預檢請求直接回應，不觸發資料庫
  if (method === 'OPTIONS') {
    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "https://saibusu.com",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
      },
      body: ""
    };
  }

  try {
    if (!prisma) {
      prisma = new PrismaClient();
    }

    // GET：只讀取，不遞增（供 chatbot 查詢用）
    if (method === 'GET') {
      const visitor = await prisma.visitor.findUnique({ where: { id: 1 } });
      return {
        statusCode: 200,
        headers: {
          "Access-Control-Allow-Origin": "https://saibusu.com",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ count: visitor.count }),
      };
    }

    // POST：遞增計數（頁面載入時觸發）
    const updatedVisitor = await prisma.visitor.update({
      where: { id: 1 },
      data: { count: { increment: 1 } },
    });

    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "https://saibusu.com",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ count: updatedVisitor.count }),
    };

  } catch (error) {
    console.error('LAMBDA_ERROR:', error);
    return {
      statusCode: 500,
      headers: { "Access-Control-Allow-Origin": "https://saibusu.com" },
      body: JSON.stringify({ error: "SERVICE_UNAVAILABLE" }),
    };
  }
};
