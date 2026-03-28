import { defineConfig } from '@prisma/config';
import 'dotenv/config'; 

export default defineConfig({
  datasource: {
    url: process.env.DATABASE_URL, // 連線資訊現在統一由這裡提供
  },
});