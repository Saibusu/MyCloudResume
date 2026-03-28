import { PrismaClient } from '@prisma/client'

// 不要在此處初始化，移到 handler 內部
let prisma;

export const handler = async (event) => {
  console.log("DEBUG - DATABASE_URL exists:", !!process.env.DATABASE_URL);
  console.log("DEBUG - DATABASE_URL length:", process.env.DATABASE_URL?.length || 0);
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
    // 軒杰，既然變數確定存在，我們直接用空括號
    // 這樣不論它是 Prisma 5, 6 還是 7，都能正確自動抓取環境變數
    if (!prisma) {
        prisma = new PrismaClient();
      }
  
      // 補上更新邏輯
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