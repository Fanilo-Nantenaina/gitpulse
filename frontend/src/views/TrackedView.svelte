<script lang="ts">
  import EmptyState from '../components/EmptyState.svelte';
  import Icon from '../components/Icon.svelte';
  import ViewHeader from '../components/ViewHeader.svelte';
  import { del, get, post, type Tracked } from '../lib/api';
  import { app } from '../lib/app.svelte';
  import { errorText } from '../lib/format';
  import { sourceLabel } from '../lib/route';
  import { Resource } from '../lib/resource.svelte';

  const list = new Resource<Tracked[]>();
  let url = $state('');
  let label = $state('');

  const load = () => list.run(() => get<Tracked[]>('/api/tracked'), true);
  $effect(() => {
    void load();
  });

  async function add(e: SubmitEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    try {
      await post('/api/tracked', { url: url.trim(), label: label.trim() || null });
      url = '';
      label = '';
      await load();
    } catch (err) {
      app.toast('error', errorText(err));
    }
  }

  async function remove(u: string) {
    try {
      await del(`/api/tracked?needle=${encodeURIComponent(u)}`);
      await load();
    } catch (err) {
      app.toast('error', errorText(err));
    }
  }
</script>

<div class="view">
  <ViewHeader icon="tracked" title={app.t('nav_tracked')} />
  <form class="card add" onsubmit={add}>
    <div class="card-h"><Icon name="plus" size={14} />{app.t('addRemote')}</div>
    <div class="card-b row">
      <label class="field grow">{app.t('gitUrl')}<input class="input mono" bind:value={url} placeholder={app.t('urlPlaceholder')} /></label>
      <label class="field">{app.t('label')}<input class="input" bind:value={label} /></label>
      <button class="btn primary" type="submit" disabled={!url.trim()}>{app.t('track')}</button>
    </div>
  </form>
  {#if list.error}
    <EmptyState icon="alert" tone="error" title={list.error} />
  {:else if list.data && !list.data.length}
    <EmptyState icon="tracked" title={app.t('noTracked')} />
  {:else if list.data}
    <section class="card">
      <table class="grid">
        <tbody>
          {#each list.data as it, i (it.url)}
            <tr>
              <td class="muted num idx">{i + 1}</td>
              <td class="name">{it.label || sourceLabel({ kind: 'url', url: it.url, insecure: false })}</td>
              <td class="mono muted">{it.url}</td>
              <td class="num">
                <button class="btn ghost sm" onclick={() => app.setSource({ kind: 'url', url: it.url, insecure: false })}>{app.t('open')}</button>
                <button class="btn ghost sm" onclick={() => remove(it.url)}><Icon name="trash" size={13} />{app.t('remove')}</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</div>

<style>
  .view {
    padding: 20px 24px 40px;
    display: grid;
    gap: 14px;
    align-content: start;
  }
  .row {
    display: flex;
    gap: 10px;
    align-items: end;
    flex-wrap: wrap;
  }
  .grow {
    flex: 1;
    min-width: 260px;
  }
  .name {
    font-weight: 600;
  }
  .idx {
    width: 32px;
  }
</style>
