// Shared autosave: 800ms debounce, then retry at 1s, 3s and 8s after failures.
const AutoSave = {
  timers: new Map(),
  versions: new Map(),
  pending: new Map(),
  cancel(key) {
    clearTimeout(this.timers.get(key));
    this.timers.delete(key);
    this.versions.set(key, (this.versions.get(key) || 0) + 1);
  },
  async settle(key) {
    this.cancel(key);
    await this.pending.get(key);
  },
  schedule(key, saveFn, onState) {
    this.cancel(key);
    const version = this.versions.get(key);
    onState?.("saving");
    this.timers.set(key, setTimeout(async () => {
      this.timers.delete(key);
      await this.pending.get(key);
      if (this.versions.get(key) !== version) return;
      const task = (async () => {
        const waits = [0, 1000, 3000, 8000];
        for (let attempt = 0; attempt < waits.length; attempt++) {
          if (waits[attempt]) await new Promise(r => setTimeout(r, waits[attempt]));
          try {
            await saveFn();
            if (this.versions.get(key) === version) onState?.("saved");
            return;
          } catch (e) {
            if (e.status === 409) {
              if (this.versions.get(key) === version) onState?.("conflict", e);
              return;
            }
            if (attempt === waits.length - 1 && this.versions.get(key) === version) {
              onState?.("failed", e);
            }
          }
        }
      })();
      this.pending.set(key, task);
      try {
        await task;
      } finally {
        if (this.pending.get(key) === task) this.pending.delete(key);
      }
    }, 800));
  }
};
