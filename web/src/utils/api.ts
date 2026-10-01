declare global { interface Window { __CHAT1_TOKEN__?: string } }

export async function api<T>(route: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(route, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Chat1-Token': window.__CHAT1_TOKEN__ || '' },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '本机服务不可用，请重新启动程序。');
  return result as T;
}

export function filePayload(file: File): Promise<{ name: string; data: string }> {
  if (file.size > 150 * 1024 * 1024) return Promise.reject(new Error('文件超过150MB，请拆分后导入。'));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取文件，请检查权限。'));
    reader.onload = () => resolve({ name: file.name, data: String(reader.result).split(',')[1] || '' });
    reader.readAsDataURL(file);
  });
}

export const errorText = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试。';
