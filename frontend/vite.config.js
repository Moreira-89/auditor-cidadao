import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Duas páginas (landing + chat), sem client-side router: mesma arquitetura de
// navegação de antes (dois HTMLs reais, cada um com seu próprio bundle),
// só que agora cada um monta uma árvore React em vez de rodar um script solto.
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        chat: resolve(__dirname, 'chat.html'),
      },
    },
  },
});
