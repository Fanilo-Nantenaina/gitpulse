<script lang="ts">
  import Icon from '../components/Icon.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { get, post } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { errorText } from '../lib/format';
  import type { Key } from '../lib/i18n';

  let keys = $state<Record<string, { set: boolean; masked: string | null }>>({});
  let drafts = $state<Record<string, string>>({});
  let starting = $state(false);

  async function loadKeys() {
    try {
      keys = await get('/api/keys');
    } catch {
      keys = {};
    }
  }

  $effect(() => {
    void loadKeys();
    if (!app.providers.length) void app.loadProviders();
  });

  const models = $derived(app.providers.find((p) => p.name === app.provider)?.models ?? []);

  async function saveKey(provider: string) {
    const key = (drafts[provider] ?? '').trim();
    if (!key) return;
    try {
      await post('/api/keys', { provider, key });
      drafts[provider] = '';
      app.toast('success', app.t('saved'));
      await Promise.all([loadKeys(), app.loadProviders()]);
    } catch (e) {
      app.toast('error', errorText(e));
    }
  }

  async function startOllama() {
    starting = true;
    try {
      const r = await post<{ started: boolean; error?: string }>('/api/ollama/start', {});
      if (!r.started) app.toast('error', r.error ?? 'Ollama');
      await app.loadProviders();
    } finally {
      starting = false;
    }
  }
</script>

<div class="view">
  <ViewHeader icon="settings" title={app.t('nav_settings')} />

  <section class="card">
    <div class="card-h"><Icon name="sparkle" size={14} />{app.t('aiProviders')}</div>
    <div class="card-b grid3">
      <label class="field">
        {app.t('provider')}
        <select class="input" value={app.provider} onchange={(e) => app.setAi(e.currentTarget.value, '', app.summaryLang)}>
          <option value="auto">{app.t('auto')}</option>
          {#each app.providers as p (p.name)}
            <option value={p.name} disabled={!p.available}>{p.name}{p.available ? '' : ` (${p.detail})`}</option>
          {/each}
          <option value="local">{app.t('localNoModel')}</option>
        </select>
      </label>
      <label class="field">
        {app.t('model')}
        <select class="input" value={app.model} onchange={(e) => app.setAi(app.provider, e.currentTarget.value, app.summaryLang)} disabled={!models.length}>
          <option value="">{app.t('modelDefault')}</option>
          {#each models as m (m)}<option value={m}>{m}</option>{/each}
        </select>
      </label>
      <label class="field">
        {app.t('summaryLang')}
        <select class="input" value={app.summaryLang} onchange={(e) => app.setAi(app.provider, app.model, e.currentTarget.value)}>
          {#each Object.entries(app.languages) as [code, name] (code)}<option value={code}>{name}</option>{/each}
        </select>
      </label>
    </div>
    <div class="provs">
      {#if !app.providersLoaded}
        <div class="prov"><span class="spinner"></span>{app.t('checking')}</div>
      {/if}
      {#each app.providers as p (p.name)}
        <div class="prov">
          <span class="dot" class:on={p.available}></span>
          <span class="pn">{p.name}</span>
          <span class="chip">{p.kind}</span>
          <span class="pd muted">{p.detail}</span>
          <div class="pact">
            {#if p.kind === 'cloud'}
              <input
                class="input mono"
                type="password"
                bind:value={drafts[p.name]}
                placeholder={`${app.t('apiKey')} (${keys[p.name]?.set ? keys[p.name]?.masked : app.t('notSet')})`}
              />
              <button class="btn sm" onclick={() => saveKey(p.name)} disabled={!drafts[p.name]?.trim()}>{app.t('save')}</button>
            {:else if p.name === 'ollama'}
              {#if p.detail === 'server not running' || p.detail === 'not installed'}
                <button class="btn sm" onclick={startOllama} disabled={starting}>
                  {#if starting}<span class="spinner"></span>{app.t('ollamaStarting')}{:else}<Icon name="play" size={12} />{app.t('startOllama')}{/if}
                </button>
              {:else if !p.models.length}
                <span class="faint small">{app.t('ollamaNoModels')} <code>ollama pull qwen2.5-coder:7b</code></span>
              {:else}
                <span class="faint small">{p.models.join(', ')}</span>
              {/if}
            {/if}
          </div>
          {#if p.kind === 'cloud' && ['gemini', 'claude', 'openai'].includes(p.name)}
            <div class="phint faint">{app.t(`hint_${p.name}` as Key)}</div>
          {/if}
        </div>
      {/each}
    </div>
  </section>

  <section class="card">
    <div class="card-h"><Icon name="sun" size={14} />{app.t('appearance')}</div>
    <div class="card-b grid3">
      <div class="field">
        {app.t('theme')}
        <div class="seg">
          <button class:on={app.theme === 'dark'} onclick={() => app.setTheme('dark')}><Icon name="moon" size={13} />{app.t('dark')}</button>
          <button class:on={app.theme === 'light'} onclick={() => app.setTheme('light')}><Icon name="sun" size={13} />{app.t('light')}</button>
        </div>
      </div>
      <div class="field">
        {app.t('language')}
        <div class="seg">
          <button class:on={app.lang === 'en'} onclick={() => app.setLang('en')}>English</button>
          <button class:on={app.lang === 'fr'} onclick={() => app.setLang('fr')}>Français</button>
        </div>
      </div>
    </div>
  </section>

  <section class="card">
    <div class="card-h"><Icon name="command" size={14} />{app.t('shortcuts')}</div>
    <div class="card-b keys">
      <span><span class="kbd">Ctrl</span> <span class="kbd">K</span></span><span>{app.t('palette')}</span>
      <span><span class="kbd">1</span>…<span class="kbd">7</span></span><span>{app.t('nav_group_repo')}</span>
      <span><span class="kbd">Ctrl</span> <span class="kbd">F</span></span><span>{app.t('graphSearch')}</span>
      <span><span class="kbd">↑</span> <span class="kbd">↓</span> <span class="kbd">Esc</span></span><span>{app.t('nav_graph')}</span>
      <span><span class="kbd">R</span></span><span>{app.t('refresh')}</span>
    </div>
  </section>
</div>

<style>
  .view {
    padding: 20px 24px 40px;
    max-width: 980px;
    display: grid;
    gap: 14px;
    align-content: start;
  }
  .grid3 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
  }
  .provs {
    border-top: 1px solid var(--border);
  }
  .prov {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
  }
  .prov:last-child {
    border-bottom: 0;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--red);
  }
  .dot.on {
    background: var(--green);
  }
  .pn {
    font-weight: 600;
    width: 64px;
  }
  .pd {
    font-size: 12px;
  }
  .pact {
    margin-left: auto;
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .pact .input {
    width: 260px;
  }
  .phint {
    width: 100%;
    font-size: 11.5px;
    padding-left: 18px;
  }
  .small {
    font-size: 12px;
  }
  .seg {
    display: flex;
    padding: 2px;
    width: fit-content;
    border-radius: var(--radius);
    background: var(--surface-2);
    border: 1px solid var(--border);
  }
  .seg button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 28px;
    padding: 0 12px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
  }
  .seg button.on {
    background: var(--bg-elev);
    color: var(--text);
    box-shadow: var(--shadow-sm);
  }
  .keys {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 8px 18px;
    align-items: center;
    color: var(--text-2);
  }
</style>
