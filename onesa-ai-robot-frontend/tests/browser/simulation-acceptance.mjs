import {expect} from '@playwright/test';

export async function isCompletedTaskResponse(response, origin, taskId) {
  try {
    const url = new URL(response.url());
    if (url.origin !== origin || url.pathname !== '/api/v1/tasks' ||
        response.request().method() !== 'GET' || response.status() !== 200) return false;
    const value = await response.json();
    return Array.isArray(value.tasks) && value.tasks.some(task => task.id === taskId && task.state === 'completed');
  } catch { return false; }
}

export async function waitForApprovedSimulationCompletion(page, taskId) {
  // Retain the original total 9s acknowledgement +6s completion budget.
  // A delayed status poll may postpone history; observe its actual owned-task
  // response before making the same DOM assertion. No extra request or retry.
  const deadline = performance.now() + 15000;
  const origin = new URL(page.url()).origin;
  const observed = page.waitForResponse(response => isCompletedTaskResponse(response, origin, taskId), {timeout: 15000})
    .then(() => ({ok: true}), error => ({ok: false, error}));
  await expect(page.locator('#notice')).toContainText('Simulation running', {timeout: 9000});
  const result = await observed;
  if (!result.ok) throw result.error;
  const remaining = deadline - performance.now();
  if (remaining <= 0) throw new Error('Completed history exceeded the existing completion budget');
  await expect(page.locator('#history li').filter({hasText: taskId}))
    .toContainText('completed', {timeout: Math.min(6000, remaining)});
}

export async function waitForSimulationReset(page) {
  await expect(page.locator('#notice')).toContainText('Simulation stop reset.', {timeout: 9000});
  await expect(page.locator('#stop-state')).toContainText('Ready');
}
