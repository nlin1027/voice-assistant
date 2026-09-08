import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  // The dev server (port 5173) serves from the root, but the production build gets
  // mounted at /app on bot.py's own server (see bot/server/bot.py) alongside Pipecat's
  // own routes -- asset URLs need that prefix baked in, or they'd resolve to the root.
  base: command === 'build' ? '/app/' : '/',
  plugins: [react(), tailwindcss()],
}));
