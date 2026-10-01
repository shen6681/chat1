import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pollJob } from '../src/utils/pollJob.ts';

test('one failed status read recovers without creating a second task', async () => {
  let reads = 0; const updates: string[] = [];
  const result = await pollJob({ id: 'existing-job', state: 'running' }, async () => {
    if (++reads === 1) throw new Error('temporary 503');
    return { id: 'existing-job', state: 'completed' };
  }, (job) => updates.push(job.state), () => true, async () => {});
  assert.equal(reads, 2); assert.equal(result.id, 'existing-job'); assert.equal(result.state, 'completed');
  assert.deepEqual(updates, ['completed']);
});
test('three failed reads report a reconnectable error instead of looping forever', async () => {
  let reads = 0;
  await assert.rejects(pollJob({ state: 'running' }, async () => { reads++; throw new Error('offline'); },
    () => {}, () => true, async () => {}), /offline/);
  assert.equal(reads, 3);
});
test('unmounted views stop polling', async () => {
  let reads = 0;
  await pollJob({ state: 'running' }, async () => { reads++; return { state: 'completed' }; },
    () => {}, () => false, async () => {});
  assert.equal(reads, 0);
});
