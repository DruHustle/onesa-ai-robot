import {test, expect} from '@playwright/test';
import {waitForApprovedSimulationCompletion} from './simulation-acceptance.mjs';

test('completion deadline starts after approval acknowledgement', async ({page}) => {
  // Every request is intercepted: no real account, backend, journal or command.
  const origin = 'https://robot-fixture.invalid';
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    if (url.pathname === '/console') return route.fulfill({contentType: 'text/html', body: '<p id="notice">Proposal created</p><ul id="history"><li>proposed · synthetic-approval-task</li></ul>'});
    if (url.pathname === '/api/v1/tasks' && route.request().method() === 'GET') return route.fulfill({contentType: 'application/json', body: JSON.stringify({tasks: [{id: 'synthetic-approval-task', state: 'completed'}]})});
    return route.abort();
  });
  await page.goto(origin + '/console');
  const requests = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) requests.push({url: request.url(), method: request.method()}); });
  await page.evaluate(() => {
    setTimeout(() => {
      document.querySelector('#notice').textContent = 'Simulation running; heartbeat must remain connected.';
      document.querySelector('#history li').textContent = 'running · synthetic-approval-task';
      setTimeout(() => {
        fetch('/api/v1/tasks').then(response => response.json()).then(value => {
          const task = value.tasks[0];
          document.querySelector('#history li').textContent = task.state + ' · ' + task.id;
        });
      }, 4000);
    }, 3000);
  });
  const premature = expect(page.locator('#history li'))
    .toContainText('completed', {timeout: 6000}).then(() => false, () => true);
  await waitForApprovedSimulationCompletion(page, 'synthetic-approval-task');
  expect(await premature).toBe(true);
  expect(requests).toEqual([{url: origin + '/api/v1/tasks', method: 'GET'}]);
});
