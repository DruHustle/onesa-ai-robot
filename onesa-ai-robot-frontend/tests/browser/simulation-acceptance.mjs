import {expect} from '@playwright/test';

export async function waitForApprovedSimulationCompletion(page, taskId) {
  // Clicking submits approval; the simulation starts after durable acknowledgement.
  await expect(page.locator('#notice')).toContainText('Simulation running');
  await expect(page.locator('#history li').filter({hasText: taskId}))
    .toContainText('completed', {timeout: 6000});
}

export async function waitForSimulationReset(page) {
  await expect(page.locator('#notice')).toContainText('Simulation stop reset.');
  await expect(page.locator('#stop-state')).toContainText('Ready');
}
