// Public and intercepted fixtures must not query protected operator endpoints.
// Cookie presence only selects test cleanup; the backend still authorizes every call.
export async function cleanupOperatorSession(page, baseURL) {
 const cookies = await page.context().cookies(new URL('/api/v1/auth/me', baseURL).href);
 if (!cookies.some(cookie => cookie.name === 'robot_session')) return;
 const options = {timeout: 10000};
 const me = await page.request.get('/api/v1/auth/me', options);
 if (me.status() === 401) return;
 if (me.status() !== 200) throw new Error('Operator cleanup session read failed');
 const session = await me.json();
 if (typeof session.csrf !== 'string' || !session.csrf) throw new Error('Operator cleanup CSRF missing');
 const signedOut = await page.request.post('/api/v1/auth/logout', {
  ...options, headers: {Origin: baseURL, 'X-CSRF-Token': session.csrf}, data: {},
 });
 if (signedOut.status() !== 200) throw new Error('Operator cleanup logout failed');
 const revoked = await page.request.get('/api/v1/auth/me', options);
 if (revoked.status() !== 401) throw new Error('Operator cleanup session remains active');
}
