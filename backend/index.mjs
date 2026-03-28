import { PrismaClient } from '@prisma/client'

// 不要在此處初始化，移到 handler 內部
let prisma;

export const handler = async (event) => {
  // --- 優先處理預檢請求，不觸發資料庫連線 ---
  if (event.requestContext?.http?.method === 'OPTIONS' || event.httpMethod === 'OPTIONS') {
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
    // 只有在真正需要時才初始化 Prisma
    if (!prisma) {
        prisma = new PrismaClient({
          datasources: {
            db: {
              url: process.env.DATABASE_URL
            }
          }
        });
      }

    const updatedVisitor = await prisma.visitor.update({
      where: { id: 1 },
      data: { count: { increment: 1 } },
    });

    return {
      statusCode: 200,
      headers: { "Access-Control-Allow-Origin": "*", "Content-Type": "application/json" },
      body: JSON.stringify({ count: updatedVisitor.count }),
    };
  } catch (error) {
    console.error('DATABASE_CONNECT_FAIL:', error.message);
    return {
      statusCode: 500,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ error: "DB_FAIL", message: error.message }),
    };
  }
};