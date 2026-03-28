import { PrismaClient } from '@prisma/client'

// Lazy singleton：在 handler 外宣告，在內初始化，利用 Lambda 執行環境重用
let prisma;

export const handler = async (event) => {

  // OPTIONS 預檢請求直接回應，不觸發資料庫
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
    const dbUrl = process.env.DATABASE_URL || '';
    console.log('DB_URL_LENGTH:', dbUrl.length);
    console.log('DB_URL_START:', dbUrl.substring(0, 30));
    console.log('DB_URL_END:', dbUrl.substring(dbUrl.length - 30));

    if (!prisma) {
      prisma = new PrismaClient();
    }

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
    console.error('LAMBDA_ERROR:', error.message);
    return {
      statusCode: 500,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ error: "DB_FAIL", message: error.message }),
    };
  }
};
