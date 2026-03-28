import { PrismaClient } from '@prisma/client'

// 軒杰：將初始化放在 handler 外部，但要確保 try-catch 能抓到它
let prisma;

export const handler = async (event) => {
  // 1. 處理 API Gateway 的 OPTIONS 預檢請求 (解決 CORS 500)
  if (event.requestContext?.http?.method === 'OPTIONS') {
    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
      },
      body: ""
    };
  }

  try {
    if (!prisma) {
      prisma = new PrismaClient();
    }

    // 2. 執行更新
    const updatedVisitor = await prisma.visitor.update({
      where: { id: 1 },
      data: { count: { increment: 1 } },
    });

    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ count: updatedVisitor.count }),
    };
  } catch (error) {
    // 3. 在日誌噴出具體原因
    console.error('CRITICAL DATABASE ERROR:', error.message);
    return {
      statusCode: 500,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ 
        error: "Database connection failed",
        details: error.message 
      }),
    };
  }
};