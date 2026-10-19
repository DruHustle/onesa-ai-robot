// Observe the existing client request, without an extra API call or retry.
// Match the existing 10-second request budget; UI assertion deadlines are unchanged.
export async function observeSessionAcknowledgement(page, path, method, action) {
 const pending = page.waitForResponse(response => new URL(response.url()).pathname === path && response.request().method() === method, {timeout:10000});
 const [response] = await Promise.all([pending, action()]);
 if(response.status() !== 200) throw new Error(`Operator session acknowledgement failed: HTTP ${response.status()}`);
 const body = await response.json();
 if(path === '/api/v1/auth/me') {
  if(typeof body?.csrf !== 'string' || !body.csrf) throw new Error('Operator session acknowledgement missing CSRF');
 } else if(path === '/api/v1/auth/logout') {
  if(body?.status !== 'signed_out') throw new Error('Operator logout acknowledgement missing signed_out');
 } else throw new Error('Unsupported operator acknowledgement');
}
export async function reloadWithSessionAcknowledgement(page) {
 await observeSessionAcknowledgement(page,'/api/v1/auth/me','GET',()=>page.reload());
}
export async function signOutWithAcknowledgement(page) {
 await observeSessionAcknowledgement(page,'/api/v1/auth/logout','POST',()=>page.getByRole('button',{name:'Sign out',exact:true}).click());
}
