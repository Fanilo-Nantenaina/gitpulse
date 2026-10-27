
import { errorText } from './format';

export class Resource<T> {
  data = $state<T | null>(null);
  error = $state<string | null>(null);
  loading = $state(false);
  #ctrl: AbortController | null = null;

  async run(fn: (signal: AbortSignal) => Promise<T>, keep = false): Promise<T | null> {
    this.#ctrl?.abort();
    const ctrl = new AbortController();
    this.#ctrl = ctrl;
    this.loading = true;
    this.error = null;
    if (!keep) this.data = null;
    try {
      const value = await fn(ctrl.signal);
      if (ctrl.signal.aborted) return null;
      this.data = value;
      return value;
    } catch (e) {
      if (ctrl.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) return null;
      this.error = errorText(e);
      return null;
    } finally {
      if (this.#ctrl === ctrl) {
        this.loading = false;
        this.#ctrl = null;
      }
    }
  }

  cancel(): void {
    this.#ctrl?.abort();
    this.#ctrl = null;
    this.loading = false;
  }

  reset(): void {
    this.cancel();
    this.data = null;
    this.error = null;
  }
}
