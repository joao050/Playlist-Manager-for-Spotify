/**
 * Playlist Manager for Spotify — Frontend Client
 * Segurança: Manipulação segura via DOM API (prevenção rigorosa contra DOM-XSS)
 */

let allTracks = [];
let filteredTracks = [];
let selectedUris = new Set();
let selectedDecades = new Set();
let selectedArtists = new Set();
let popularityFilter = 'all';

let currentPage = 1;
const PAGE_SIZE = 50;

// Inicialização ao carregar o DOM
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadUser();
  loadTracksAndStats();
});

function setupEventListeners() {
  // Sincronizar e LGPD
  const btnSync = document.getElementById('btn-sync');
  if (btnSync) btnSync.addEventListener('click', syncLibrary);

  const btnDeleteData = document.getElementById('btn-delete-data');
  if (btnDeleteData) btnDeleteData.addEventListener('click', deleteMyData);

  // Filtros
  const btnReset = document.getElementById('btn-reset-filters');
  if (btnReset) btnReset.addEventListener('click', resetFilters);

  const inputSearch = document.getElementById('input-search');
  if (inputSearch) inputSearch.addEventListener('input', applyFilters);

  const inputArtist = document.getElementById('input-artist');
  if (inputArtist) inputArtist.addEventListener('input', applyFilters);

  const popAll = document.getElementById('pop-all');
  if (popAll) popAll.addEventListener('click', () => setPopularityFilter('all'));

  const popHits = document.getElementById('pop-hits');
  if (popHits) popHits.addEventListener('click', () => setPopularityFilter('hits'));

  const popIndie = document.getElementById('pop-indie');
  if (popIndie) popIndie.addEventListener('click', () => setPopularityFilter('indie'));

  const yearMin = document.getElementById('year-min');
  if (yearMin) yearMin.addEventListener('input', applyFilters);

  const yearMax = document.getElementById('year-max');
  if (yearMax) yearMax.addEventListener('input', applyFilters);

  // Ações de tabela e seleção
  const btnSelectAll = document.getElementById('btn-select-all');
  if (btnSelectAll) btnSelectAll.addEventListener('click', toggleSelectAll);

  const checkMaster = document.getElementById('check-master');
  if (checkMaster) checkMaster.addEventListener('change', () => toggleMasterCheck(checkMaster));

  const btnPrev = document.getElementById('btn-prev');
  if (btnPrev) btnPrev.addEventListener('click', () => changePage(-1));

  const btnNext = document.getElementById('btn-next');
  if (btnNext) btnNext.addEventListener('click', () => changePage(1));

  // Modais de Criação
  const btnOpenCreate = document.getElementById('btn-open-create');
  if (btnOpenCreate) btnOpenCreate.addEventListener('click', openCreateModal);

  const btnMobileCreate = document.getElementById('btn-mobile-create');
  if (btnMobileCreate) btnMobileCreate.addEventListener('click', openCreateModal);

  const btnCloseModal = document.getElementById('btn-close-modal');
  if (btnCloseModal) btnCloseModal.addEventListener('click', closeCreateModal);

  const btnCancelModal = document.getElementById('btn-cancel-modal');
  if (btnCancelModal) btnCancelModal.addEventListener('click', closeCreateModal);

  const btnConfirmCreate = document.getElementById('btn-confirm-create');
  if (btnConfirmCreate) btnConfirmCreate.addEventListener('click', confirmCreatePlaylist);
}

// ─── CARREGAR PERFIL DO USUÁRIO ──────────────────────────────────────────────
async function loadUser() {
  const userNameEl = document.getElementById('user-name');
  try {
    const res = await fetch('/api/user');
    if (res.status === 401) {
      window.location.href = '/login-page';
      return;
    }
    const data = await res.json();
    if (data.authenticated) {
      userNameEl.textContent = data.display_name || 'Conectado';
      const images = data.images || [];
      if (images.length > 0) {
        const avatar = document.getElementById('user-avatar');
        avatar.src = images[images.length - 1].url;
        avatar.classList.remove('hidden');
        document.getElementById('user-avatar-icon').classList.add('hidden');
      }
    }
  } catch (e) {
    if (userNameEl) userNameEl.textContent = 'Conectado';
  }
}

// ─── CARREGAR MÚSICAS & ESTATÍSTICAS ──────────────────────────────────────────
async function loadTracksAndStats() {
  const tbody = document.getElementById('track-table-body');
  
  // Exibir loading seguro via DOM
  tbody.textContent = '';
  const trLoad = document.createElement('tr');
  const tdLoad = document.createElement('td');
  tdLoad.colSpan = 6;
  tdLoad.className = 'text-center py-12 text-neutral-400';

  const spinner = document.createElement('i');
  spinner.className = 'fa-solid fa-spinner fa-spin text-2xl text-[#1DB954] mb-3 block';

  tdLoad.appendChild(spinner);
  tdLoad.appendChild(document.createTextNode('Carregando suas músicas curtidas... isso pode levar alguns instantes.'));
  trLoad.appendChild(tdLoad);
  tbody.appendChild(trLoad);

  try {
    const res = await fetch('/api/tracks');
    if (res.status === 401) {
      window.location.href = '/login-page';
      return;
    }
    const data = await res.json();
    allTracks = data.tracks || [];
    document.getElementById('count-total').textContent = allTracks.length;
    allTracks.forEach(t => selectedUris.add(t.uri));

    loadStats();
    applyFilters();
  } catch (e) {
    tbody.textContent = '';
    const trErr = document.createElement('tr');
    const tdErr = document.createElement('td');
    tdErr.colSpan = 6;
    tdErr.className = 'text-center py-8 text-red-400';
    tdErr.textContent = `Erro ao carregar músicas: ${e.message || e}`;
    trErr.appendChild(tdErr);
    tbody.appendChild(trErr);
  }
}

// ─── FILTROS DINÂMICOS ────────────────────────────────────────────────────────
function toggleDecade(decade, btn) {
  if (selectedDecades.has(decade)) {
    selectedDecades.delete(decade);
    btn.classList.remove('bg-[#1DB954]', 'text-black', 'font-bold');
    btn.classList.add('bg-[#282828]', 'text-neutral-300');
  } else {
    selectedDecades.add(decade);
    btn.classList.remove('bg-[#282828]', 'text-neutral-300');
    btn.classList.add('bg-[#1DB954]', 'text-black', 'font-bold');
  }
  applyFilters();
}

function toggleArtistChip(artist, chip) {
  if (selectedArtists.has(artist)) {
    selectedArtists.delete(artist);
    chip.classList.remove('border-[#1DB954]', 'text-[#1DB954]');
  } else {
    selectedArtists.add(artist);
    chip.classList.add('border-[#1DB954]', 'text-[#1DB954]');
  }
  const countLabel = document.getElementById('selected-artists-count');
  countLabel.textContent = selectedArtists.size > 0 ? `${selectedArtists.size} selecionados` : '';
  applyFilters();
}

function setPopularityFilter(type) {
  popularityFilter = type;
  ['all', 'hits', 'indie'].forEach(t => {
    const btn = document.getElementById(`pop-${t}`);
    if (!btn) return;
    if (t === type) {
      btn.classList.add('bg-[#282828]', 'text-white');
      btn.classList.remove('text-neutral-400');
    } else {
      btn.classList.remove('bg-[#282828]', 'text-white');
      btn.classList.add('text-neutral-400');
    }
  });
  applyFilters();
}

function resetFilters() {
  document.getElementById('input-search').value = '';
  document.getElementById('input-artist').value = '';
  document.getElementById('year-min').value = '';
  document.getElementById('year-max').value = '';
  selectedDecades.clear();
  selectedArtists.clear();
  popularityFilter = 'all';

  document.querySelectorAll('#decades-container button').forEach(b => {
    b.className = 'text-[11px] px-2.5 py-1 rounded-full bg-[#282828] text-neutral-300 hover:text-white border border-transparent transition';
  });
  document.querySelectorAll('#top-artists-container button').forEach(b => {
    b.classList.remove('border-[#1DB954]', 'text-[#1DB954]');
  });
  document.getElementById('selected-artists-count').textContent = '';
  setPopularityFilter('all');
  applyFilters();
}

function applyFilters() {
  const search = document.getElementById('input-search').value.toLowerCase().trim();
  const artistInput = document.getElementById('input-artist').value.toLowerCase().trim();
  const yMin = parseInt(document.getElementById('year-min').value, 10) || null;
  const yMax = parseInt(document.getElementById('year-max').value, 10) || null;

  filteredTracks = allTracks.filter(t => {
    if (search) {
      const matchName = t.name && t.name.toLowerCase().includes(search);
      const matchAlbum = t.album && t.album.toLowerCase().includes(search);
      if (!matchName && !matchAlbum) return false;
    }

    if (selectedDecades.size > 0 && !selectedDecades.has(t.decade)) {
      return false;
    }

    if (artistInput) {
      const inputArtists = artistInput.split(',').map(a => a.trim()).filter(Boolean);
      const match = t.artists && t.artists.some(a => inputArtists.some(inp => a.toLowerCase().includes(inp)));
      if (!match) return false;
    }

    if (selectedArtists.size > 0) {
      const matchSelected = t.artists && t.artists.some(a => selectedArtists.has(a));
      if (!matchSelected) return false;
    }

    if (yMin || yMax) {
      const y = parseInt(t.release_year, 10);
      if (isNaN(y)) return false;
      if (yMin && y < yMin) return false;
      if (yMax && y > yMax) return false;
    }

    if (popularityFilter === 'hits' && t.popularity < 60) return false;
    if (popularityFilter === 'indie' && t.popularity > 45) return false;

    return true;
  });

  document.getElementById('count-filtered').textContent = filteredTracks.length;
  const mobileCountEl = document.getElementById('mobile-count');
  if (mobileCountEl) mobileCountEl.textContent = filteredTracks.length;

  let summaryParts = [];
  if (selectedDecades.size > 0) summaryParts.push(`Décadas: ${Array.from(selectedDecades).join(', ')}`);
  if (selectedArtists.size > 0) summaryParts.push(`Artistas: ${Array.from(selectedArtists).join(', ')}`);
  if (search) summaryParts.push(`Termo: "${search}"`);
  document.getElementById('filter-summary').textContent = summaryParts.length > 0 ? summaryParts.join(' • ') : 'Mostrando todas as músicas curtidas';

  currentPage = 1;
  renderTable();
}

// ─── RENDERIZAÇÃO SEGURA DA TABELA (DOM API) ──────────────────────────────────
function renderTable() {
  const tbody = document.getElementById('track-table-body');
  tbody.textContent = '';

  const start = (currentPage - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, filteredTracks.length);
  const pageItems = filteredTracks.slice(start, end);

  if (pageItems.length === 0) {
    const trEmpty = document.createElement('tr');
    const tdEmpty = document.createElement('td');
    tdEmpty.colSpan = 6;
    tdEmpty.className = 'text-center py-8 text-neutral-500';
    tdEmpty.textContent = 'Nenhuma música encontrada para os filtros atuais.';
    trEmpty.appendChild(tdEmpty);
    tbody.appendChild(trEmpty);
    document.getElementById('page-info').textContent = '0 de 0';
    return;
  }

  pageItems.forEach(t => {
    const isChecked = selectedUris.has(t.uri);
    const tr = document.createElement('tr');
    tr.className = 'bg-card-hover transition group';

    // 1. Checkbox
    const tdCheck = document.createElement('td');
    tdCheck.className = 'py-2.5 px-3 text-center';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = isChecked;
    checkbox.className = 'accent-[#1DB954] cursor-pointer';
    checkbox.addEventListener('change', () => toggleTrackCheck(t.uri, checkbox));
    tdCheck.appendChild(checkbox);
    tr.appendChild(tdCheck);

    // 2. Título (prevenção DOM-XSS via textContent)
    const tdTitle = document.createElement('td');
    tdTitle.className = 'py-2.5 px-3 font-medium text-white max-w-[200px] truncate';
    const spanTitle = document.createElement('span');
    spanTitle.title = t.name || '';
    spanTitle.textContent = t.name || '';
    tdTitle.appendChild(spanTitle);
    tr.appendChild(tdTitle);

    // 3. Artista
    const tdArtist = document.createElement('td');
    tdArtist.className = 'py-2.5 px-3 text-neutral-300 max-w-[150px] truncate';
    const spanArtist = document.createElement('span');
    spanArtist.title = t.artists_str || '';
    spanArtist.textContent = t.artists_str || '';
    tdArtist.appendChild(spanArtist);
    tr.appendChild(tdArtist);

    // 4. Álbum
    const tdAlbum = document.createElement('td');
    tdAlbum.className = 'py-2.5 px-3 text-neutral-400 max-w-[150px] truncate hidden md:table-cell';
    const spanAlbum = document.createElement('span');
    spanAlbum.title = t.album || '';
    spanAlbum.textContent = t.album || '';
    tdAlbum.appendChild(spanAlbum);
    tr.appendChild(tdAlbum);

    // 5. Ano
    const tdYear = document.createElement('td');
    tdYear.className = 'py-2.5 px-3 text-center text-neutral-400';
    const spanYear = document.createElement('span');
    spanYear.className = 'bg-[#121212] px-2 py-0.5 rounded text-[11px]';
    spanYear.textContent = t.release_year || '';
    tdYear.appendChild(spanYear);
    tr.appendChild(tdYear);

    // 6. Popularidade
    const tdPop = document.createElement('td');
    tdPop.className = 'py-2.5 px-3 text-center hidden sm:table-cell';
    const spanPop = document.createElement('span');
    spanPop.className = 'text-neutral-400 font-mono text-[11px]';
    spanPop.textContent = `${t.popularity ?? 0}%`;
    tdPop.appendChild(spanPop);
    tr.appendChild(tdPop);

    tbody.appendChild(tr);
  });

  document.getElementById('page-info').textContent = `Mostrando ${start + 1}-${end} de ${filteredTracks.length}`;
  document.getElementById('btn-prev').disabled = currentPage === 1;
  document.getElementById('btn-next').disabled = end >= filteredTracks.length;
}

function changePage(delta) {
  currentPage += delta;
  renderTable();
  window.scrollTo({ top: 300, behavior: 'smooth' });
}

function toggleTrackCheck(uri, checkbox) {
  if (checkbox.checked) {
    selectedUris.add(uri);
  } else {
    selectedUris.delete(uri);
  }
}

function toggleSelectAll() {
  const btn = document.getElementById('btn-select-all');
  const allSelected = filteredTracks.every(t => selectedUris.has(t.uri));
  if (allSelected) {
    filteredTracks.forEach(t => selectedUris.delete(t.uri));
    btn.textContent = 'Selecionar Todas';
  } else {
    filteredTracks.forEach(t => selectedUris.add(t.uri));
    btn.textContent = 'Desmarcar Todas';
  }
  renderTable();
}

function toggleMasterCheck(masterCheckbox) {
  const isChecked = masterCheckbox.checked;
  filteredTracks.forEach(t => {
    if (isChecked) selectedUris.add(t.uri);
    else selectedUris.delete(t.uri);
  });
  renderTable();
}

// ─── SINCRONIZAÇÃO DA BIBLIOTECA ──────────────────────────────────────────────
async function syncLibrary() {
  const btn = document.getElementById('btn-sync');
  const icon = document.getElementById('sync-icon');
  icon.classList.add('fa-spin');
  btn.disabled = true;

  try {
    await fetch('/api/sync', { method: 'POST' });
    allTracks = [];
    selectedUris.clear();
    filteredTracks = [];
    await loadTracksAndStats();
  } catch (e) {
    alert(`Erro ao conectar com servidor: ${e.message || e}`);
  } finally {
    icon.classList.remove('fa-spin');
    btn.disabled = false;
  }
}

function loadStats() {
  const decadeCount = {};
  const artistCount = {};
  allTracks.forEach(t => {
    const dec = t.decade || 'Desconhecido';
    if (dec !== 'Desconhecido') decadeCount[dec] = (decadeCount[dec] || 0) + 1;
    (t.artists || []).forEach(a => {
      if (a) artistCount[a] = (artistCount[a] || 0) + 1;
    });
  });

  // Renderizar botões de décadas de forma segura
  const decContainer = document.getElementById('decades-container');
  decContainer.textContent = '';
  Object.entries(decadeCount).sort().forEach(([dec, count]) => {
    const btn = document.createElement('button');
    btn.className = 'text-[11px] px-2.5 py-1 rounded-full bg-[#282828] text-neutral-300 hover:text-white border border-transparent transition';
    btn.textContent = `${dec} (${count})`;
    btn.dataset.decade = dec;
    btn.addEventListener('click', () => toggleDecade(dec, btn));
    decContainer.appendChild(btn);
  });

  // Renderizar chips de top artistas
  const artContainer = document.getElementById('top-artists-container');
  artContainer.textContent = '';
  Object.entries(artistCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .forEach(([artist, count]) => {
      const chip = document.createElement('button');
      chip.className = 'text-[10px] px-2 py-0.5 rounded-md bg-[#222] text-neutral-400 hover:text-white border border-neutral-800 transition truncate max-w-[140px]';
      chip.textContent = `${artist} (${count})`;
      chip.addEventListener('click', () => toggleArtistChip(artist, chip));
      artContainer.appendChild(chip);
    });
}

// ─── MODAL DE CRIAÇÃO DE PLAYLIST ─────────────────────────────────────────────
function openCreateModal() {
  const activeUris = filteredTracks.map(t => t.uri).filter(uri => selectedUris.has(uri));
  if (activeUris.length === 0) {
    alert('Selecione pelo menos uma música para criar a playlist!');
    return;
  }

  document.getElementById('modal-track-count').textContent = `${activeUris.length} faixas`;

  let suggestedName = "Minha Seleção";
  if (selectedDecades.size === 1) {
    suggestedName = `Curtidas dos ${Array.from(selectedDecades)[0]}`;
  } else if (selectedArtists.size === 1) {
    suggestedName = `Especial ${Array.from(selectedArtists)[0]}`;
  } else if (selectedDecades.size > 0 && selectedArtists.size > 0) {
    suggestedName = `${Array.from(selectedArtists).join(' & ')} (${Array.from(selectedDecades)[0]})`;
  }
  document.getElementById('modal-name').value = suggestedName;
  document.getElementById('modal-status').classList.add('hidden');
  document.getElementById('modal-create').classList.remove('hidden');
}

function closeCreateModal() {
  document.getElementById('modal-create').classList.add('hidden');
}

async function confirmCreatePlaylist() {
  const name = document.getElementById('modal-name').value.trim();
  const desc = document.getElementById('modal-desc').value.trim();
  const isPublic = document.getElementById('modal-public').checked;
  const activeUris = filteredTracks.map(t => t.uri).filter(uri => selectedUris.has(uri));

  if (!name) {
    alert('Digite um nome para a playlist.');
    return;
  }

  const btn = document.getElementById('btn-confirm-create');
  const statusBox = document.getElementById('modal-status');
  btn.disabled = true;

  btn.textContent = '';
  const spinIcon = document.createElement('i');
  spinIcon.className = 'fa-solid fa-spinner fa-spin mr-1';
  btn.appendChild(spinIcon);
  btn.appendChild(document.createTextNode(' Criando...'));

  statusBox.className = 'text-xs p-3 rounded-lg bg-neutral-800 text-neutral-300 block';
  statusBox.textContent = `Enviando ${activeUris.length} músicas para o Spotify...`;

  try {
    const res = await fetch('/api/create_playlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        description: desc,
        is_public: isPublic,
        track_uris: activeUris
      })
    });

    const data = await res.json();
    if (data.success) {
      statusBox.className = 'text-xs p-3 rounded-lg bg-emerald-950 text-emerald-400 border border-emerald-800 block';
      statusBox.textContent = '';

      const divTitle = document.createElement('div');
      divTitle.className = 'font-bold mb-1';
      divTitle.textContent = '🎉 Playlist criada com sucesso!';

      const divTotal = document.createElement('div');
      divTotal.textContent = `${data.total_added} músicas adicionadas à sua conta.`;

      statusBox.appendChild(divTitle);
      statusBox.appendChild(divTotal);

      // Link seguro com rel noopener e validação de protocolo
      if (data.playlist_url && (data.playlist_url.startsWith('https://') || data.playlist_url.startsWith('http://'))) {
        const link = document.createElement('a');
        link.href = data.playlist_url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'inline-block mt-2 spotify-green text-black font-bold px-3 py-1.5 rounded text-xs hover:underline';

        const spIcon = document.createElement('i');
        spIcon.className = 'fa-brands fa-spotify mr-1';
        link.appendChild(spIcon);
        link.appendChild(document.createTextNode(' Abrir no Spotify'));
        statusBox.appendChild(link);
      }

      btn.textContent = 'Concluído';
    } else {
      statusBox.className = 'text-xs p-3 rounded-lg bg-red-950 text-red-400 border border-red-800 block';
      statusBox.textContent = `Erro: ${data.error}`;
      btn.disabled = false;
      btn.textContent = 'Tentar Novamente';
    }
  } catch (e) {
    statusBox.className = 'text-xs p-3 rounded-lg bg-red-950 text-red-400 border border-red-800 block';
    statusBox.textContent = `Erro de conexão: ${e.message || e}`;
    btn.disabled = false;
    btn.textContent = 'Tentar Novamente';
  }
}

// ─── LGPD ART. 18: EXCLUSÃO DE DADOS ──────────────────────────────────────────
async function deleteMyData() {
  const confirmDelete = confirm(
    "LGPD — Exclusão Definitiva de Dados:\n\n" +
    "Esta ação excluirá imediatamente todos os seus tokens de acesso, dados temporários e cache criptografado armazenados nesta aplicação.\n\n" +
    "Deseja realmente excluir todos os seus dados e desconectar?"
  );
  if (!confirmDelete) return;

  try {
    const res = await fetch('/api/delete_my_data', { method: 'POST' });
    if (res.ok) {
      window.location.href = '/login-page?deleted=1';
    } else {
      alert('Não foi possível excluir os dados automaticamente. Tente sair normalmente.');
    }
  } catch (e) {
    window.location.href = '/login-page?deleted=1';
  }
}
