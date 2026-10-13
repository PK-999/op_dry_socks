/* Cancellable JSON requests, shared by dashboard flows. */
(() => {
  'use strict';

async function api(path, {body, signal, timeout = 70000} = {}) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', cancel, {once: true});
  const timer = setTimeout(cancel, timeout);
  try {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      ...(body === undefined ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}),
      signal: controller.signal,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `The server returned ${response.status}. Please try again.`);
    return result;
  } catch (error) {
    if (error.name === 'AbortError' && !signal?.aborted) throw new Error('This check took too long. Please refresh to try again.');
    if (error instanceof SyntaxError) throw new Error('The local server returned an unreadable response. Please try again.');
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}
  window.DrySocksAPI = {request: api};
})();
