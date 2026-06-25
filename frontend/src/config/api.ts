// URL base da API. Em desenvolvimento local usa a variável de ambiente VITE_API_URL;
// em produção (Vercel), cai no fallback apontando para o backend no Render.
export const API_URL = import.meta.env.VITE_API_URL || 'https://comparador-precos-yiqd.onrender.com'
