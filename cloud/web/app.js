/* Mobile web counterpart to Imprint's Convert and Listen audiobook workspace. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const base = location.pathname.startsWith('/cloud/') ? '/cloud' : '';
  const api = path => base + path;
  const player = $('player');
  const state = {books: [], audiobooks: [], jobs: [], book: null, file: null,
                 estimated: null, lastSavedMs: -1, saving: Promise.resolve(),
                 marks: [], sleepTimer: null, lastSyncAt: 0};

  async function request(path, options = {}) {
    const response = await fetch(api(path), {credentials: 'same-origin', ...options});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    return payload;
  }

  function message(id, value) { $(id).textContent = value; }
  function fail(id, error) { message(id, error instanceof Error ? error.message : String(error)); }

  function showTab(name) {
    document.querySelectorAll('.tab').forEach(tab => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('.pane').forEach(pane => pane.classList.toggle('active', pane.id === name));
    if (name === 'listen') refreshLibrary();
  }
  document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => showTab(tab.dataset.tab)));

  function selectBook(book) {
    state.book = book;
    state.estimated = null;
    message('selectedBook', book ? book.drive_path : 'No ebook selected');
    message('estimate', book ? 'Estimate the cost before converting.' : 'Select a book to see an estimate.');
    $('estimateButton').disabled = !book;
    $('convertButton').disabled = true;
    renderBooks();
  }

  function renderBooks() {
    const query = $('bookSearch').value.trim().toLowerCase();
    const matching = state.books.filter(book => book.drive_path.toLowerCase().includes(query));
    message('bookCount', `${matching.length} matching ebooks · showing ${Math.min(50, matching.length)}`);
    const container = $('bookResults');
    container.replaceChildren();
    for (const book of matching.slice(0, 50)) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'book-row' + (state.book?.drive_path === book.drive_path ? ' selected' : '');
      row.setAttribute('role', 'option');
      row.setAttribute('aria-selected', String(state.book?.drive_path === book.drive_path));
      const label = document.createElement('span');
      const title = document.createElement('b');
      title.textContent = book.name;
      const path = document.createElement('small');
      path.textContent = book.drive_path;
      label.append(title, path);
      row.append(label);
      row.addEventListener('click', () => selectBook(book));
      container.append(row);
    }
    if (!matching.length) container.textContent = 'No ebooks match this search.';
  }

  async function refreshBooks() {
    message('bookCount', 'Loading ebooks from Google Drive…');
    try {
      state.books = (await request('/api/books')).books;
      const wanted = new URLSearchParams(location.search).get('book');
      if (wanted && !state.book) {
        const match = state.books.find(book => book.drive_path === wanted);
        if (match) selectBook(match);
      }
      renderBooks();
    } catch (error) { fail('bookCount', error); }
  }

  async function estimate() {
    if (!state.book) return;
    $('estimateButton').disabled = true;
    message('estimate', 'Reading the ebook and estimating audio length…');
    try {
      const result = await request('/api/estimate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({drive_path: state.book.drive_path}),
      });
      state.estimated = result;
      message('estimate', `About ${result.minutes} min audio · estimated OpenAI cost $${result.estimated_usd.toFixed(2)}. ${result.pricing_note}`);
      $('convertButton').disabled = false;
    } catch (error) {
      state.estimated = null;
      fail('estimate', error);
    } finally { $('estimateButton').disabled = false; }
  }

  async function convert() {
    if (!state.book || !state.estimated) return;
    const chunkTokens = Number($('chunkTokens').value);
    if (!Number.isInteger(chunkTokens) || chunkTokens < 300 || chunkTokens > 1500) {
      message('estimate', 'Chunk size must be between 300 and 1500 tokens.');
      return;
    }
    const name = state.book.name;
    if (!confirm(`Convert ${name}? Estimated OpenAI text-to-speech cost: $${state.estimated.estimated_usd.toFixed(2)}. Actual charges may differ.`)) return;
    $('convertButton').disabled = true;
    try {
      const result = await request('/api/jobs', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({drive_path: state.book.drive_path,
                              voice: $('voice').value, chunk_tokens: chunkTokens}),
      });
      message('estimate', result.already_exists
        ? `This book is already ${result.status}. Check Conversions or Listen.`
        : 'Queued in the cloud. Your Mac can be off. Check Conversions for its status.');
      await refreshJobs();
    } catch (error) { fail('estimate', error); }
    finally { $('convertButton').disabled = false; }
  }

  function renderJobs() {
    const container = $('jobs');
    container.replaceChildren();
    if (!state.jobs.length) { container.textContent = 'No conversions yet.'; return; }
    for (const job of state.jobs) {
      const row = document.createElement('div');
      row.className = 'job';
      const title = document.createElement('b');
      title.textContent = job.drive_path || 'Untitled';
      const status = document.createElement('small');
      status.className = job.status === 'failed' ? 'failed' : '';
      status.textContent = `${job.status}${job.voice ? ' · ' + job.voice : ''}${job.error ? ' · ' + job.error : ''}`;
      row.append(title, status);
      if (job.status === 'finished' && job.audio_id) {
        const button = document.createElement('button');
        button.className = 'button subtle';
        button.type = 'button';
        button.textContent = 'Listen';
        button.addEventListener('click', async () => {
          showTab('listen');
          const file = state.audiobooks.find(item => item.id === job.audio_id);
          if (file) openFile(file);
          else {
            await refreshLibrary();
            const refreshed = state.audiobooks.find(item => item.id === job.audio_id);
            if (refreshed) openFile(refreshed);
          }
        });
        row.append(button);
      }
      container.append(row);
    }
  }

  async function refreshJobs() {
    try {
      state.jobs = (await request('/api/jobs')).jobs;
      renderJobs();
    } catch (error) { $('jobs').textContent = `Could not load conversions: ${error.message}`; }
  }

  function renderAudiobooks() {
    const query = $('audioSearch').value.trim().toLowerCase();
    const matching = state.audiobooks.filter(file => file.name.toLowerCase().includes(query));
    message('audioCount', `${matching.length} matching audiobooks · showing ${Math.min(50, matching.length)}`);
    const container = $('audioResults');
    container.replaceChildren();
    for (const file of matching.slice(0, 50)) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'audio-row';
      const title = document.createElement('span');
      title.textContent = file.name;
      row.append(title);
      row.addEventListener('click', () => openFile(file));
      container.append(row);
    }
    if (!matching.length) container.textContent = 'No audiobooks match this search.';
  }

  async function refreshLibrary() {
    try {
      state.audiobooks = (await request('/api/library')).audiobooks;
      renderAudiobooks();
    } catch (error) { fail('audioCount', error); }
  }

  function saveProgress() {
    if (!state.file || player.readyState < HTMLMediaElement.HAVE_METADATA ||
        player.currentSrc !== new URL(api(`/api/audio/${encodeURIComponent(state.file.id)}`), location.href).href ||
        !Number.isFinite(player.currentTime)) return state.saving;
    const position = Math.round(player.currentTime * 1000);
    if (position === state.lastSavedMs) return state.saving;
    state.lastSavedMs = position;
    const file = state.file;
    state.saving = state.saving.catch(() => {}).then(() => request(`/api/progress/${encodeURIComponent(file.id)}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, keepalive: true,
      body: JSON.stringify({position_ms: position,
                            duration_ms: Math.round((player.duration || 0) * 1000),
                            title: file.name.replace(/\.mp3$/i, '')}),
    })).catch(error => {
      state.lastSavedMs = -1;
      message('playerStatus', `Progress could not sync: ${error.message}`);
    });
    return state.saving;
  }

  async function openFile(file) {
    if (state.file) await saveProgress();
    player.pause();
    state.file = null;
    player.removeAttribute('src');
    player.load();
    state.file = file;
    state.lastSavedMs = -1;
    message('nowPlaying', file.name);
    message('playerStatus', 'Loading saved position…');
    $('addMark').disabled = false;
    $('back30').disabled = false;
    $('forward30').disabled = false;
    const link = $('downloadAudio');
    link.href = api(`/api/audio/${encodeURIComponent(file.id)}`);
    link.download = file.name;
    link.hidden = false;
    try {
      const progress = await request(`/api/progress/${encodeURIComponent(file.id)}`);
      state.marks = progress.marks || [];
      renderMarks();
      player.src = api(`/api/audio/${encodeURIComponent(file.id)}`);
      player.onloadedmetadata = () => {
        const seconds = progress.finished ? 0 : Number(progress.position_ms || 0) / 1000;
        if (seconds > 0 && seconds < player.duration - 2) player.currentTime = seconds;
        message('playerStatus', `Ready to play. ${seconds ? 'Resuming near ' + Math.round(seconds / 60) + ' min.' : 'Starting at the beginning.'}`);
      };
    } catch (error) { fail('playerStatus', error); }
  }

  function formatTime(ms) {
    const seconds = Math.floor(ms / 1000);
    return `${Math.floor(seconds / 3600)}:${String(Math.floor(seconds / 60) % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }

  function renderMarks() {
    const container = $('marks');
    container.replaceChildren();
    if (!state.marks.length) return;
    const heading = document.createElement('h4');
    heading.textContent = 'Saved marks';
    container.append(heading);
    for (const mark of state.marks) {
      const row = document.createElement('div');
      row.className = 'mark';
      const jump = document.createElement('button');
      jump.type = 'button';
      jump.textContent = `${formatTime(mark.position_ms)} · ${mark.title}`;
      jump.addEventListener('click', () => { player.currentTime = mark.position_ms / 1000; });
      const remove = document.createElement('button');
      remove.className = 'delete';
      remove.type = 'button';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove mark ${mark.title}`);
      remove.addEventListener('click', async () => {
        try {
          state.marks = (await request(`/api/marks/${encodeURIComponent(state.file.id)}/${mark.position_ms}`,
                                       {method: 'DELETE'})).marks;
          renderMarks();
        } catch (error) { fail('playerStatus', error); }
      });
      row.append(jump, remove);
      container.append(row);
    }
  }

  async function addMark() {
    if (!state.file) return;
    const position = Math.round(player.currentTime * 1000);
    const title = prompt('Name this listening mark', `Mark at ${formatTime(position)}`);
    if (!title?.trim()) return;
    try {
      state.marks = (await request(`/api/marks/${encodeURIComponent(state.file.id)}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({position_ms: position, title: title.trim()}),
      })).marks;
      renderMarks();
    } catch (error) { fail('playerStatus', error); }
  }

  function armSleep() {
    clearTimeout(state.sleepTimer);
    const minutes = Number($('sleep').value);
    if (minutes && !player.paused) {
      state.sleepTimer = setTimeout(() => {
        player.pause();
        saveProgress();
        $('sleep').value = '0';
      }, minutes * 60000);
    }
  }

  $('bookSearch').addEventListener('input', renderBooks);
  $('audioSearch').addEventListener('input', renderAudiobooks);
  $('refreshBooks').addEventListener('click', refreshBooks);
  $('refreshJobs').addEventListener('click', refreshJobs);
  $('refreshLibrary').addEventListener('click', refreshLibrary);
  $('estimateButton').addEventListener('click', estimate);
  $('convertButton').addEventListener('click', convert);
  $('addMark').addEventListener('click', addMark);
  $('back30').addEventListener('click', () => { player.currentTime = Math.max(0, player.currentTime - 30); });
  $('forward30').addEventListener('click', () => { player.currentTime = Math.min(player.duration || Infinity, player.currentTime + 30); });
  $('speed').addEventListener('change', () => { player.playbackRate = Number($('speed').value); });
  $('sleep').addEventListener('change', armSleep);
  player.addEventListener('play', armSleep);
  player.addEventListener('pause', () => { clearTimeout(state.sleepTimer); saveProgress(); });
  player.addEventListener('ended', saveProgress);
  player.addEventListener('timeupdate', () => {
    if (Date.now() - state.lastSyncAt >= 15000) {
      state.lastSyncAt = Date.now();
      saveProgress();
    }
  });
  window.addEventListener('pagehide', saveProgress);
  setInterval(() => { if (!player.paused) saveProgress(); }, 15000);
  setInterval(() => {
    if (document.visibilityState === 'visible' && !$('workspace').hidden) refreshJobs();
  }, 20000);

  $('connectButton').href = api('/auth/start?next=%2Fcloud%2Fapp');
  (async () => {
    try {
      const session = await request('/api/session');
      $('connectPanel').hidden = !!session.connected;
      $('workspace').hidden = !session.connected;
      message('connection', session.connected ? `Connected · ${session.email}` : 'Google Drive not connected');
      if (session.connected) await Promise.all([refreshBooks(), refreshJobs(), refreshLibrary()]);
    } catch (error) {
      $('connectPanel').hidden = false;
      fail('connection', error);
    }
  })();
})();
