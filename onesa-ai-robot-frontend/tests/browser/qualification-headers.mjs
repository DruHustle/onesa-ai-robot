// Hosting-only UI is outside the application under test. This header changes no
// project settings, CSP, application authorization or production configuration.
export function qualificationHeaders(origin, bypass = '') {
 const headers = {'x-vercel-skip-toolbar': '1'};
 if (!bypass) return headers;
 if (!/^https:\/\/onesa-ai-robot-[a-z0-9-]+\.vercel\.app$/.test(origin)) {
  throw new Error('Automation credential requires the verified Robot Preview origin');
 }
 return {...headers, 'x-vercel-protection-bypass': bypass};
}
