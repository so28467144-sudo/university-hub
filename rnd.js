'use strict';
// R&D 공고 메뉴: NTIS 국가R&D통합공고를 NTIS와 같은 카테고리(공고현황·부처명·공고유형·공고형태·공고규모·마감일)로 보여 줍니다.
// 공고 데이터는 rnd-announcements.json에서 읽습니다. 이 파일은 rnd_collector.py가 NTIS RSS로 30분마다 채웁니다.
// RSS에 없는 공고유형·공고형태는 데이터 파일에 카테고리가 있을 때만 필터로 보여 줍니다.

// 한국 시간 기준 날짜(YYYY-MM-DD)
function rndKoreanDay(value) {
  const stamp = new Date(value).getTime();
  return Number.isNaN(stamp) ? '' : new Date(stamp + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}
// 마감일까지 남은 날짜. 마감일 당일은 0, 지났으면 음수, 마감일이 없으면 null입니다.
function rndDday(closeDate, today) {
  if (!closeDate || !today) return null;
  const close = Date.parse(String(closeDate).slice(0, 10) + 'T00:00:00Z');
  const now = Date.parse(today + 'T00:00:00Z');
  return Number.isNaN(close) || Number.isNaN(now) ? null : Math.round((close - now) / 86400000);
}
// 공고현황: 접수 시작일·마감일과 오늘 날짜로 계산합니다(페이지를 오래 열어 두어도 맞도록). 날짜가 없으면 저장된 값을 씁니다.
function rndStatus(item, today) {
  const open = String(item.open_date || '').slice(0, 10);
  const close = String(item.close_date || '').slice(0, 10);
  if (!today || (!open && !close)) return item.status || '';
  if (close && close < today) return '마감';
  if (open && open > today) return '접수예정';
  return '접수중';
}
// 공고금액 표시: 1억 이상은 억 단위, 그 미만은 만원 단위
function rndBudgetLabel(won) {
  if (won === null || won === undefined || won === '' || Number.isNaN(Number(won)) || Number(won) <= 0) return '';
  const amount = Number(won);
  if (amount >= 100000000) return `${Math.round(amount / 10000000) / 10}억원`;
  return `${Math.round(amount / 10000).toLocaleString('ko-KR')}만원`;
}
function rndDdayLabel(dday) {
  if (dday === null) return '';
  if (dday < 0) return '마감';
  return dday === 0 ? 'D-Day' : `D-${dday}`;
}
// NTIS 마감일 필터 구간
function rndDeadlineBucket(dday) {
  if (dday === null || dday < 0) return '';
  if (dday <= 3) return '마감3일전';
  if (dday <= 7) return '마감1주전';
  if (dday <= 21) return '마감3주전';
  if (dday <= 30) return '마감1달전';
  return '마감1달이상';
}
// NTIS 공고규모 필터 구간(원 단위 금액)
function rndScaleBucket(won) {
  if (won === null || won === undefined || won === '' || Number.isNaN(Number(won))) return '';
  const amount = Number(won);
  if (amount < 100000000) return '1억미만';
  if (amount < 300000000) return '1억이상 ~ 3억미만';
  if (amount < 500000000) return '3억이상 ~ 5억미만';
  return '5억이상';
}
// 필터: 같은 갈래 안에서는 하나라도 맞으면(또는), 갈래끼리는 모두 맞아야(그리고) 보여 줍니다.
function rndFilter(items, filters, today) {
  const query = String(filters.query || '').normalize('NFKC').toLowerCase().replace(/\s+/g, '');
  const pick = (set, value) => !set || set.size === 0 || set.has(value);
  return items.filter(item => {
    const dday = rndDday(item.close_date, today);
    if (!pick(filters.status, rndStatus(item, today))) return false;
    if (!pick(filters.ministry, item.ministry)) return false;
    if (!pick(filters.type, item.type)) return false;
    if (!pick(filters.form, item.form)) return false;
    if (!pick(filters.scale, rndScaleBucket(item.budget_won))) return false;
    if (!pick(filters.deadline, rndDeadlineBucket(dday))) return false;
    if (query) {
      const text = [item.title, item.ministry, item.agency].join(' ').normalize('NFKC').toLowerCase().replace(/\s+/g, '');
      if (!text.includes(query)) return false;
    }
    return true;
  });
}
// 정렬: 마감 임박순(마감된 공고와 마감일 없는 공고는 뒤로) 또는 최신 공고순
function rndSort(items, order, today) {
  const rows = [...items];
  if (order === 'latest') return rows.sort((a, b) => String(b.posted_date || '').localeCompare(String(a.posted_date || '')));
  const key = item => {
    const dday = rndDday(item.close_date, today);
    return dday === null ? 1e9 : dday < 0 ? 1e8 - dday : dday;
  };
  return rows.sort((a, b) => key(a) - key(b) || String(b.posted_date || '').localeCompare(String(a.posted_date || '')));
}

(function setupRnd() {
  if (typeof document === 'undefined' || !document.getElementById('rnd')) return;
  const $r = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const allGroups = [
    ['status', '공고현황'], ['ministry', '부처명'], ['type', '공고유형'], ['form', '공고형태'], ['scale', '공고규모'], ['deadline', '마감일'],
  ];
  // 데이터 파일에 카테고리 목록이 있는 갈래만 필터로 보여 줍니다.
  let groups = allGroups;
  const filters = { query: '', order: 'deadline', status: new Set(), ministry: new Set(), type: new Set(), form: new Set(), scale: new Set(), deadline: new Set() };
  let data = { categories: {}, items: [], status: 'loading' };
  let limit = 20;

  // 메뉴 전환: R&D 공고를 누르면 대학 소식 영역을 숨기고 공고 영역을 보여 줍니다.
  const showRnd = on => {
    document.body.dataset.view = on ? 'rnd' : '';
    $r('news').hidden = on;
    $r('rnd').hidden = !on;
    $r('rndNews').classList.toggle('active', on);
    $r('rndNews').setAttribute('aria-current', on ? 'page' : 'false');
    if (on) {
      $r('allNews').classList.remove('active');
      $r('savedNews').classList.remove('active');
      render();
      $r('rnd').scrollIntoView({ block: 'start' });
    }
  };
  $r('rndNews').addEventListener('click', () => showRnd(true));
  // 대학 소식·관심 소식으로 돌아갈 때는 누른 메뉴를 선택 표시합니다(기사 화면이 먼저 그려지므로 여기서 맞춥니다).
  for (const id of ['allNews', 'savedNews']) {
    $r(id).addEventListener('click', () => {
      showRnd(false);
      $r('allNews').classList.toggle('active', id === 'allNews');
      $r('savedNews').classList.toggle('active', id === 'savedNews');
    });
  }

  function renderFilters() {
    const counts = {};
    const today = rndKoreanDay(Date.now());
    for (const item of data.items) {
      const values = { status: rndStatus(item, today), ministry: item.ministry, type: item.type, form: item.form,
        scale: rndScaleBucket(item.budget_won), deadline: rndDeadlineBucket(rndDday(item.close_date, today)) };
      for (const [key, value] of Object.entries(values)) if (value) counts[key + '|' + value] = (counts[key + '|' + value] || 0) + 1;
    }
    // 카테고리마다 한 줄: 왼쪽에 카테고리 이름, 오른쪽에 선택 항목을 두고 위아래로 쌓습니다.
    $r('rndFilters').replaceChildren(...groups.map(([key, label]) => {
      const box = document.createElement('div');
      box.className = 'rnd-group';
      box.setAttribute('role', 'group');
      box.setAttribute('aria-label', label);
      const title = document.createElement('span');
      title.className = 'rnd-group-title';
      title.textContent = label;
      const list = document.createElement('div');
      list.className = 'rnd-group-chips';
      const options = data.categories[key] || [];
      const chips = options.map(value => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'rnd-chip';
        const count = counts[key + '|' + value] || 0;
        chip.innerHTML = `${esc(value)}${data.items.length ? ` <span>${count}</span>` : ''}`;
        chip.setAttribute('aria-pressed', String(filters[key].has(value)));
        chip.onclick = () => {
          filters[key].has(value) ? filters[key].delete(value) : filters[key].add(value);
          limit = 20;
          render();
        };
        return chip;
      });
      list.append(...chips);
      box.append(title, list);
      return box;
    }));
  }

  function render() {
    renderFilters();
    const today = rndKoreanDay(Date.now());
    const rows = rndSort(rndFilter(data.items, filters, today), filters.order, today);
    const active = groups.some(([key]) => filters[key].size) || filters.query;
    $r('rndCount').innerHTML = `공고 <b>${rows.length.toLocaleString('ko-KR')}</b>건`;
    $r('rndResetFilters').hidden = !active;
    const source = data.source || {};
    $r('rndStatus').innerHTML = data.status === 'awaiting_api'
      ? `${esc(data.status_note || '')} 지금은 <a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">NTIS 원문 목록</a>에서 확인할 수 있습니다.`
      : data.status === 'error'
        ? `공고 정보를 불러오지 못했습니다. <a href="${esc(source.url || 'https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do')}" target="_blank" rel="noopener noreferrer">NTIS 원문 목록</a>에서 확인해 주세요.`
        : data.status === 'loading' ? '공고 정보를 불러오고 있습니다.'
          : `출처: <a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.name || 'NTIS 국가R&D통합공고')}</a>${data.updated_at ? ` · 마지막 갱신 ${esc(rndKoreanDay(data.updated_at))}` : ''}`;
    $r('rndList').replaceChildren(...rows.slice(0, limit).map(item => {
      const dday = rndDday(item.close_date, today);
      const card = document.createElement('article');
      card.className = 'rnd-card';
      const status = rndStatus(item, today);
      const statusClass = { 접수중: 'open', 접수예정: 'soon', 마감: 'closed' }[status] || 'closed';
      const urgent = dday !== null && dday >= 0 && dday <= 7;
      const link = /^https:\/\//.test(item.url || '') ? item.url : '';
      card.innerHTML =
        `<div class="rnd-card-top"><span class="rnd-status rnd-status-${statusClass}">${esc(status || '현황 미상')}</span>` +
        `${item.type ? `<span class="rnd-tag">${esc(item.type)}</span>` : ''}${item.form ? `<span class="rnd-tag">${esc(item.form)}</span>` : ''}` +
        `${dday !== null ? `<span class="rnd-dday${urgent ? ' urgent' : ''}">${rndDdayLabel(dday)}</span>` : ''}</div>` +
        `<h3>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a>` : esc(item.title)}</h3>` +
        `<p class="rnd-meta"><strong>${esc(item.ministry || '부처 미상')}</strong>${item.agency ? `<span>${esc(item.agency)}</span>` : ''}` +
        `${item.open_date ? `<span>접수 ${esc(String(item.open_date).slice(0, 10))}</span>` : ''}` +
        `${item.close_date ? `<span>마감 ${esc(String(item.close_date).slice(0, 10))}</span>` : ''}` +
        `${rndBudgetLabel(item.budget_won) ? `<span>${esc(rndBudgetLabel(item.budget_won))}</span>` : ''}</p>`;
      return card;
    }));
    $r('rndEmpty').hidden = rows.length > 0;
    $r('rndEmptyTitle').textContent = data.items.length ? '조건에 맞는 공고가 없어요' : (data.status === 'loading' ? '공고를 불러오는 중이에요' : '아직 표시할 공고가 없어요');
    $r('rndEmptyText').textContent = data.items.length ? '다른 부처나 공고현황을 선택해 보세요.' : 'NTIS RSS에서 공고를 받아오면 이곳에 표시됩니다.';
    $r('rndMore').hidden = rows.length <= limit;
  }

  $r('rndSearch').addEventListener('input', event => { filters.query = event.target.value; limit = 20; render(); });
  $r('rndSort').addEventListener('change', event => { filters.order = event.target.value; render(); });
  $r('rndMore').addEventListener('click', () => { limit += 20; render(); });
  $r('rndResetFilters').addEventListener('click', () => {
    groups.forEach(([key]) => filters[key].clear());
    filters.query = '';
    $r('rndSearch').value = '';
    limit = 20;
    render();
  });

  fetch('./rnd-announcements.json', { cache: 'no-store' })
    .then(response => { if (!response.ok) throw new Error('HTTP ' + response.status); return response.json(); })
    .then(json => {
      data = { ...json, items: Array.isArray(json.items) ? json.items : [], categories: json.categories || {} };
      groups = allGroups.filter(([key]) => Array.isArray(data.categories[key]) && data.categories[key].length);
    })
    .catch(() => { data = { ...data, status: 'error' }; })
    .finally(() => { if (document.body.dataset.view === 'rnd') render(); else renderFilters(); });
})();
