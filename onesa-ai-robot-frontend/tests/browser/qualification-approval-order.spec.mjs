import {test, expect} from '@playwright/test';
import {waitForApprovedSimulationCompletion} from './simulation-acceptance.mjs';

test('completion deadline starts after approval acknowledgement', async ({page}) => {
  // Local DOM fixture only: no account, API, journal or control requests.
  await page.setContent('<p id="notice">Proposal created</p><ul id="history"><li>proposed · synthetic-approval-task</li></ul>');
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  await page.evaluate(() => {
    setTimeout(() => {
      document.querySelector('#notice').textContent = 'Simulation running; heartbeat must remain connected.';
      document.querySelector('#history li').textContent = 'running · synthetic-approval-task';
      setTimeout(() => {
        document.querySelector('#history li').textContent = 'completed · synthetic-approval-task';
      }, 4000);
    }, 3000);
  });
  const premature = expect(page.locator('#history li'))
    .toContainText('completed', {timeout: 6000}).then(() => false, () => true);
  await waitForApprovedSimulationCompletion(page, 'synthetic-approval-task');
  expect(await premature).toBe(true);
  expect(requests).toEqual([]);
});
