/** Retry status reads only. Creating a paid task is never repeated by this helper. */
export async function pollJob<T extends { state: string }>(
  initial: T, read: () => Promise<T>, update: (value: T) => void,
  active: () => boolean, wait = () => new Promise<void>((resolve) => setTimeout(resolve, 700)),
): Promise<T> {
  let latest = initial; let errors = 0;
  while (latest.state === 'running' && active()) {
    await wait(); if (!active()) break;
    try { latest = await read(); errors = 0; update(latest); }
    catch (error) { if (++errors >= 3) throw error; }
  }
  return latest;
}
