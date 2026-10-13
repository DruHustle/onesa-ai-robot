// Vercel rewrites add their route parameter to the query string.
import {handler} from '../server.mjs';
export default async function gateway(req, res) {
  const url = new URL(req.url || '/', 'http://frontend.invalid');
  const binding = url.searchParams.getAll('__onesa_route');
  // Strip only the exact original-path binding. Preserve all client query keys.
  if (url.pathname.startsWith('/api/v1/') && binding.length === 1 &&
      binding[0] === url.pathname.slice('/api/v1/'.length)) {
    url.searchParams.delete('__onesa_route');
    req.url = url.pathname + url.search;
  }
  return handler(req, res);
}
