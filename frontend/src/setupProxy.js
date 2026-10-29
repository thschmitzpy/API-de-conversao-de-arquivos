const { createProxyMiddleware } = require('http-proxy-middleware');

// Só no `npm start`. Em produção o nginx faz o mesmo papel (etapa 3).
const target = process.env.CONVERSOR_API_URL || 'http://localhost:8000';
const apiKey = process.env.CONVERSOR_API_KEY;

module.exports = function setupProxy(app) {
  if (!apiKey) {
    console.warn('[setupProxy] CONVERSOR_API_KEY nao definida: a API vai responder 401.');
  }

  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
      pathRewrite: { '^/api': '' },
      onProxyReq: (proxyReq) => {
        if (apiKey) {
          proxyReq.setHeader('X-API-Key', apiKey);
        }
      },
    })
  );
};
