const http = require('http');

const TARGET = 'http://localhost:8081';
const PORT = 8083;

const proxy = http.createServer((req, res) => {
  const options = {
    hostname: 'localhost',
    port: 8081,
    path: req.url,
    method: req.method,
    headers: req.headers
  };

  // Add CORS headers
  res.setHeader('Access-Control-Allow-Origin', 'http://localhost:8082');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, x-api-key');
  res.setHeader('Access-Control-Allow-Credentials', 'true');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  req.pipe(proxyReq, { end: true });
});

proxy.listen(PORT, () => {
  console.log(`CORS proxy running on http://localhost:${PORT}`);
});
