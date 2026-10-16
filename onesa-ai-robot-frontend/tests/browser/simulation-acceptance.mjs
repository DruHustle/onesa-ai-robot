import {expect} from '@playwright/test';

export async function waitForApprovedSimulationCompletion(page, taskId) {
  // Clicking submits approval; the simulation starts after durable acknowledgement.
  // The gateway allows eight seconds for a bounded acknowledgement; the client
  // still cancels at ten seconds. Completion/freshness limits stay unchanged.
  await expect(page.locator('#notice')).toContainText('Simulation running', {timeout: 9000});
  await expect(page.locator('#history li').filter({hasText: taskId}))
    .toContainText('completed', {timeout: 6000});
}

export async function waitForSimulationReset(page) {
  await expect(page.locator('#notice')).toContainText('Simulation stop reset.', {timeout: 9000});
  await expect(page.locator('#stop-state')).toContainText('Ready');
}
