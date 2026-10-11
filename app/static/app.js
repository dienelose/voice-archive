'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {
  wave:'M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4',
  grid:'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',
  check:'m5 12 4 4L19 6', checkCircle:'M22 11a10 10 0 1 1-6-9m-9 9 4 4L22 4',
  plus:'M12 5v14M5 12h14', arrow:'M5 12h14m-5-5 5 5-5 5', chevron:'m9 5 7 7-7 7',
  upload:'M12 16V3m-5 5 5-5 5 5M4 16v4h16v-4',
  file:'M14 2H5v20h14V7zm0 0v5h5M8 12h8m-8 4h6',
  folder:'M3 7h7l2-3h9v16H3z', search:'M21 21l-5-5m2-6a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
  clock:'M12 8v5l3 2m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  shield:'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6zm-5 10 3 3 6-6',
  settings:'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1zm6 9a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  help:'M9 9a3 3 0 1 1 5 2c-2 1-2 1-2 3m0 3h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  copy:'M9 9h12v12H9zM5 15H3V3h12v2', download:'M12 3v13m-5-5 5 5 5-5M3 17v4h18v-4',
  close:'m6 6 12 12M6 18 18 6', play:'m8 4 12 8-12 8z', pause:'M8 4v16M16 4v16',
  back:'m11 5-7 7 7 7M5 12h15', rewind:'m11 5-9 7 9 7zm11 0-9 7 9 7z',
  forward:'m2 5 9 7-9 7zm11 0 9 7-9 7z', repeat:'m17 2 4 4-4 4M3 11V6h18M7 22l-4-4 4-4m14-1v5H3',
  edit:'m16 3 5 5-12 12-6 1 1-6zm-3 3 5 5', trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
  spark:'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3z', mic:'M8 4a4 4 0 0 1 8 0v8a4 4 0 0 1-8 0zm-4 6v2a8 8 0 0 0 16 0v-2M12 20v3m-4 0h8',
  save:'M3 3h15l3 3v15H3zm4 0v7h9V3M7 21v-7h10v7', history:'M3 3v6h6M3 9a9 9 0 1 1 0 6m9-9v6l4 2',
  monitor:'M2 3h20v14H2zm10 14v4m-5 0h10', lock:'M5 10h14v12H5zm3 0V6a4 4 0 0 1 8 0v4',
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
const time = n => { n = Math.floor(Number(n) || 0); return `${n >= 3600 ? `${Math.floor(n/3600)}:` : ''}${String(Math.floor(n%3600/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`; };
const date = value => new Date(value).toLocaleDateString('ko-KR',{year:'numeric',month:'2-digit',day:'2-digit'});
const statuses = {uploaded:['분석 대기',''],queued:['처리 대기','orange'],converting:['오디오 준비','orange'],transcribing:['음성인식 중','orange'],diarizing:['화자 구분 중','orange'],canceling:['중지 중','orange'],paused:['일시 중지',''],completed:['검토 가능','green'],error:['확인 필요','red']};
const draftNames = {summary:'주제별 요약',mayor:'시장님 주요 발언',article:'기사 초안',report:'보고서 초안',polished:'읽기 좋게 정리한 녹취'};
const busyStates = ['queued','converting','transcribing','diarizing','canceling'];
const state = {page:'library', projects:[], project:null, filter:'전체', search:'', tab:'reference', segmentSearch:'', segmentFilter:'all', health:null, settings:null, prompt:'', audioId:null, repeat:null};
const saves = new Map();
const failedSaves = new Map();
const dirtySegments = new Set();
const referenceBuffers = new Map();
let toastTimer, pollBusy = false;

async function api(url, options = {}) {
  const headers = {'X-Voice-Archive':'1', ...(options.headers || {})};
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch('/api' + url, {...options, headers});
  if (!response.ok) {
    let message = `요청에 실패했습니다 (${response.status}).`;
    try { const payload = await response.json(); message = typeof payload.detail === 'string' ? payload.detail : '입력 내용을 확인해 주세요.'; } catch {}
    throw new Error(message);
  }
  return response.json();
}
function toast(message) {
  $('#toast').textContent = message; $('#toast').classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 4300);
}
function showModal(title, body) {
  $('#modal').innerHTML = `<div class="modal-head"><h2 id="modal-title">${esc(title)}</h2><button class="icon-btn" data-action="close-modal" aria-label="닫기">${icon('close')}</button></div><div class="modal-body">${body}</div>`;
  if (!$('#modal').open) $('#modal').showModal();
}
async function copyPrompt() {
  if (!state.prompt) state.prompt = (await api('/reference-prompt')).text;
  try { await navigator.clipboard.writeText(state.prompt); toast('프롬프트를 복사했습니다. ChatGPT에 자료와 함께 붙여넣어 주세요.'); }
  catch { showModal('분석 프롬프트', `<textarea class="reference-text" style="width:100%" readonly>${esc(state.prompt)}</textarea><p class="muted small">텍스트를 선택해 복사해 주세요.</p>`); }
}
function shell(content, detail = false) {
  const completed = state.projects.filter(p => p.segment_count && p.reviewed_count === p.segment_count).length;
  $('#app').innerHTML = `<aside class="sidebar">
    <a class="brand" href="#library" aria-label="목소리 기록실 홈"><div class="brand-mark">${icon('wave')}</div><div><div class="brand-name">목소리 기록실</div><small>VOICE ARCHIVE</small></div></a>
    <span class="nav-label">WORKSPACE</span>
    <button class="nav-item ${state.page==='library'||state.page==='detail'?'active':''}" data-action="library">${icon('grid')}<span>녹음 보관함</span><span class="count">${state.projects.length}</span></button>
    <button class="nav-item" data-action="reviewed-library">${icon('checkCircle')}<span>검토 완료</span><span class="count">${completed}</span></button>
    <span class="nav-label" style="margin-top:25px">TOOLS</span>
    <button class="nav-item ${state.page==='guide'?'active':''}" data-action="guide">${icon('help')}<span>사용 가이드</span></button>
    <button class="nav-item ${state.page==='settings'?'active':''}" data-action="settings">${icon('settings')}<span>로컬 환경 설정</span></button>
    <div class="sidebar-note"><strong>${icon('shield')} 내 PC 안의 기록실</strong>녹음과 녹취록은 이 PC에 저장됩니다. AI 처리도 로컬에서 진행합니다.</div>
    <div class="profile"><div class="avatar">나</div><div>개인 작업 공간<small>LOCAL WORKSPACE</small></div></div>
  </aside><main id="main" class="main ${detail?'detail-main':''}">
    <header class="topbar"><div class="breadcrumb"><span>개인 작업 공간</span>${icon('chevron')}<strong>${{library:'녹음 보관함',detail:'녹취 작업실',guide:'사용 가이드',settings:'로컬 환경 설정'}[state.page]}</strong></div><div class="local-status"><span class="dot"></span>이 PC에서만 사용${icon('monitor')}</div></header>${content}</main>`;
  document.body.classList.toggle('has-player', detail);
  $('#player').hidden = !detail;
}
function statusTag(p) { const [label,color] = statuses[p.status] || [p.status,'']; return `<span class="tag ${color}">${busyStates.includes(p.status)?'<span class="dot"></span>':''}${label}</span>`; }
function renderLibrary() {
  const items = state.projects.filter(p => (!state.search || (p.title + p.filename + p.kind).toLowerCase().includes(state.search.toLowerCase())) &&
    (state.filter==='전체' || state.filter==='검토 완료' && p.segment_count>0 && p.segment_count===p.reviewed_count || p.kind===state.filter));
  const totalSeconds = state.projects.reduce((n,p) => n+p.duration,0);
  const completed = state.projects.filter(p => p.segment_count && p.segment_count===p.reviewed_count).length;
  shell(`<section class="greeting"><div><div class="eyebrow">YOUR WORDS, WELL KEPT.</div><h1>말의 순간을, 기록의 자산으로.</h1><p>소중한 발언을 듣고, 확인하고, 오래 남길 수 있도록.</p></div><button class="btn primary" data-action="upload">${icon('plus')}새 녹음 추가</button></section>
    <section class="hero-grid"><div class="upload-card" id="drop-zone"><div class="upload-symbol">${icon('upload')}</div><div><h2>어떤 이야기를 기록할까요?</h2><p>녹음 파일을 여기에 놓거나 선택해 주세요.</p><button class="btn small soft" data-action="upload">파일 선택${icon('arrow')}</button></div><span class="hint">MP3 · WAV · M4A · FLAC 외 / 최대 4GB</span></div>
    <div class="context-card"><div class="context-art">${icon('file')}</div><div><span class="eyebrow">BEFORE YOU BEGIN</span><h3>맥락을 알면,<br>기록은 더 정확해집니다.</h3><p>ChatGPT에서 정리한 사전 자료를<br>참고정보로 함께 준비해 보세요.</p></div><button class="text-link" data-action="guide">사전 자료 준비하는 방법${icon('arrow')}</button></div></section>
    <section class="stats"><div class="stat"><div class="stat-icon">${icon('folder')}</div><div><div class="stat-label">보관 중인 녹음</div><div class="stat-value">${state.projects.length}<span>개</span></div></div></div><div class="stat"><div class="stat-icon">${icon('clock')}</div><div><div class="stat-label">함께 담은 시간</div><div class="stat-value">${Math.floor(totalSeconds/3600)}<span>시간</span> ${Math.floor(totalSeconds%3600/60)}<span>분</span></div></div></div><div class="stat"><div class="stat-icon">${icon('checkCircle')}</div><div><div class="stat-label">검토를 마친 기록</div><div class="stat-value">${completed}<span>개</span></div></div></div></section>
    <section><div class="library-head"><h2>나의 녹음 <span class="muted small">${state.projects.length}</span></h2><label class="search">${icon('search')}<input id="library-search" aria-label="녹음 검색" placeholder="제목, 파일명으로 검색" value="${esc(state.search)}"></label></div>
    <div class="filters">${['전체','타운홀 미팅','회의','현장 발언',...(state.filter==='검토 완료'?['검토 완료']:[])].map(f=>`<button class="filter ${state.filter===f?'active':''}" data-action="filter" data-value="${f}">${f}</button>`).join('')}</div>
    <div class="recordings" id="recording-list">${items.length?items.map(p=>`<button class="recording" data-action="open-project" data-id="${p.id}"><span class="recording-symbol">${icon(p.kind==='현장 발언'?'mic':'wave')}</span><div><h3>${esc(p.title)}</h3><div class="recording-meta"><span>${esc(p.kind)}</span><span>${date(p.created_at)}</span><span>${time(p.duration)}</span>${p.reference?'<span>참고정보 포함</span>':''}</div></div><div class="recording-right">${p.peaks.length?`<div class="mini-wave" aria-hidden="true">${p.peaks.slice(0,18).map(v=>`<span style="height:${Math.max(3,v*90)}px"></span>`).join('')}</div>`:''}${statusTag(p)}<span class="arrow">${icon('chevron')}</span></div></button>`).join(''):
      `<div class="empty-state"><div class="empty-icon">${icon(state.search?'search':'wave')}</div><h3>${state.projects.length?'조건에 맞는 녹음이 없습니다':'첫 번째 이야기를 기다리고 있어요'}</h3><p>${state.projects.length?'검색어나 분류를 바꿔 보세요.':'타운홀 미팅, 회의, 현장의 목소리까지.<br>녹음 파일을 추가해 나만의 기록을 시작하세요.'}</p>${state.projects.length?'':'<button class="btn soft" data-action="upload">첫 녹음 추가하기</button>'}</div>`}</div></section>
    <div class="dashboard-foot">${icon('lock')}원본은 그대로, 기록은 더 선명하게. 모든 작업은 내 PC에서.</div>`);
  const drop = $('#drop-zone');
  for (const event of ['dragenter','dragover']) drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add('dragover');});
  for (const event of ['dragleave','drop']) drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove('dragover');});
  drop.addEventListener('drop',e=>openUpload(e.dataTransfer.files[0]));
}
function openUpload(selectedFile = null) {
  showModal('새 녹음 추가', `<form id="upload-form"><label class="file-picker">${icon('upload')}<strong>녹음 파일을 선택해 주세요</strong><small>파일은 외부 서버로 전송되지 않습니다.</small><input id="upload-file" type="file" name="file" accept=".mp3,.wav,.m4a,.flac,.ogg,.mp4" required></label>
    <div class="field"><label for="upload-title">기록 제목</label><input id="upload-title" name="title" placeholder="예: 10월 주민과의 대화" maxlength="160"></div>
    <div class="field"><label for="upload-kind">녹음 유형</label><select id="upload-kind" name="kind"><option>타운홀 미팅</option><option>회의</option><option>현장 발언</option></select></div>
    <details><summary class="small muted">사전 참고정보 함께 붙여넣기 (선택)</summary><div class="field" style="margin-top:12px"><label for="upload-reference">ChatGPT에서 분석한 결과</label><textarea id="upload-reference" name="reference" rows="5" maxlength="100000" placeholder="분석 결과의 1~8번 구역 전체를 붙여넣어 주세요."></textarea></div></details>
    <div id="upload-progress" class="upload-progress" role="status"></div><div class="modal-footer"><button type="button" class="btn" data-action="close-modal">취소</button><button type="submit" class="btn primary">${icon('plus')}기록실에 추가</button></div></form>`);
  if (selectedFile) { const transfer = new DataTransfer(); transfer.items.add(selectedFile); $('#upload-file').files = transfer.files; $('#upload-title').value = selectedFile.name.replace(/\.[^.]+$/,''); }
  $('#upload-file').addEventListener('change',()=>{if (!$('#upload-title').value && $('#upload-file').files[0]) $('#upload-title').value=$('#upload-file').files[0].name.replace(/\.[^.]+$/,'');});
  $('#upload-form').addEventListener('submit', e => {
    e.preventDefault(); const form=e.currentTarget; const file=$('#upload-file').files[0]; if(!file)return;
    if(file.size>4*1024**3){toast('파일 한 개는 최대 4GB까지 지원합니다.');return;}
    $$('button',form).forEach(b=>b.disabled=true);
    const xhr=new XMLHttpRequest(); xhr.open('POST','/api/projects');xhr.setRequestHeader('X-Voice-Archive','1');
    xhr.upload.onprogress=event=>{if(event.lengthComputable)$('#upload-progress').textContent=`PC 작업 폴더에 복사 중 · ${Math.round(event.loaded/event.total*100)}%`;};
    xhr.onload=async()=>{try{const payload=JSON.parse(xhr.responseText);if(xhr.status>=400)throw new Error(typeof payload.detail==='string'?payload.detail:'파일을 추가하지 못했습니다.');$('#modal').close();toast('녹음을 추가했습니다. 참고정보를 확인한 뒤 인식을 시작해 주세요.');await refreshProjects();location.hash=`project/${payload.id}`;}catch(err){$('#upload-progress').textContent=err.message;$$('button',form).forEach(b=>b.disabled=false);}};
    xhr.onerror=()=>{$('#upload-progress').textContent='파일을 복사하지 못했습니다. 앱 연결을 확인해 주세요.';$$('button',form).forEach(b=>b.disabled=false);};
    xhr.send(new FormData(form));
  });
}
function speakerOptions(selected = '') {
  const keys = new Set(['speaker_1',...Object.keys(state.project.speakers),...state.project.segments.map(s=>s.speaker)]);
  return [...keys].map((key,index)=>`<option value="${esc(key)}" ${key===selected?'selected':''}>${esc(state.project.speakers[key] || `화자 ${index+1} (미지정)`)}</option>`).join('');
}
function renderSegments() {
  const p=state.project;
  const segments=p.segments.filter(s=>(state.segmentFilter!=='review' || !s.reviewed)&&(state.segmentFilter!=='flagged'||s.flags.length)&&(!state.segmentSearch || s.text.includes(state.segmentSearch)));
  if (!p.segments.length) return `<div class="empty-state" style="border:0;border-radius:0"><div class="empty-icon">${icon('wave')}</div><h3>${busyStates.includes(p.status)?'목소리를 글로 옮기고 있습니다':'녹취를 시작할 준비가 되었나요?'}</h3><p>${busyStates.includes(p.status)?'첫 구간이 완료되면 이곳에 발언이 나타납니다.<br>이 화면을 열어둔 채 기다려 주세요.':'오른쪽에서 참고정보와 용어를 확인한 뒤<br>상단의 ‘음성인식 시작’을 눌러 주세요.'}</p></div>`;
  if(!segments.length)return '<div class="empty-state" style="border:0"><p>해당하는 발언이 없습니다.</p></div>';
  return segments.map(s=>`<article class="segment" id="segment-${s.id}" data-start="${s.start}" data-end="${s.end}"><div class="segment-top"><select class="speaker-select" data-speaker="${s.id}" aria-label="발언 화자">${speakerOptions(s.speaker)}</select><button class="time-link" data-action="seek" data-time="${s.start}" title="이 발언 듣기">${time(s.start)} — ${time(s.end)}</button><span class="spacer"></span><span class="save-indicator" id="saved-${s.id}"></span><button class="icon-btn" data-action="repeat-segment" data-id="${s.id}" aria-label="이 구간 반복 재생">${icon('repeat')}</button></div>
    <textarea data-segment="${s.id}" rows="${Math.min(8,Math.max(2,Math.ceil(s.text.length/42)))}" aria-label="${time(s.start)} 발언 편집">${esc(s.text)}</textarea>
    ${s.flags.length?`<div class="flags">${s.flags.map(f=>`<span class="flag">· ${esc(f)}</span>`).join('')}</div>`:''}
    <div class="segment-bottom"><details class="original"><summary>자동 녹취 원문</summary><p>${esc(s.original_text)}</p><button class="text-link" data-action="history" data-id="${s.id}">수정 이력 보기</button></details><button class="review-btn ${s.reviewed?'done':''}" data-action="review" data-id="${s.id}">${icon('check')}${s.reviewed?'검토 완료':'검토 완료 표시'}</button></div></article>`).join('');
}
function renderSide() {
  const p=state.project;
  const buffer=referenceBuffers.get(p.id)||p;
  if(state.tab==='reference')return `<h3>맥락을 함께 준비해 주세요</h3><p>ChatGPT에서 사전 자료를 분석한 결과를 붙여넣으세요. 자료는 실제 발언과 구분해 참고합니다.</p><button class="text-link" data-action="copy-prompt">${icon('copy')}ChatGPT 분석 프롬프트 복사</button><div class="divider" style="margin:20px 0"></div>
    <form id="reference-form"><div class="field"><label for="reference">사전 참고정보</label><textarea id="reference" class="reference-text" maxlength="100000" placeholder="행사 계획서·참석자·사업 설명자료를 분석한 결과 전체를 붙여넣으세요.">${esc(buffer.reference)}</textarea><small>원문을 덮어쓰는 정답이 아닌, 인식과 검토를 돕는 참고정보입니다.</small></div>
    <div class="field"><div class="row spread"><label for="terms" class="small">음성인식에 참고할 용어</label><button type="button" class="text-link" style="padding:0" data-action="extract-terms">8번 구역에서 가져오기</button></div><textarea id="terms" rows="3" maxlength="400" placeholder="인명, 지명, 정확한 사업명…">${esc(buffer.terms)}</textarea><small>중요한 용어부터 쉼표로 구분해 주세요. 최대 400자.</small></div>
    <button class="btn primary" type="submit" ${busyStates.includes(p.status)?'disabled':''}>${icon('save')}참고정보 저장</button></form>`;
  if(state.tab==='speakers') {
    const keys=[...new Set(['speaker_1',...Object.keys(p.speakers),...p.segments.map(s=>s.speaker)])];
    return `<h3>누구의 목소리인가요?</h3><p>녹음을 듣고 화자 이름을 지정해 주세요. 이름만으로 목소리를 자동 식별하지 않습니다.</p><div class="notice">${p.diarization_status==='completed'?'자동 구분된 화자는 틀릴 수 있습니다. 겹치는 발언을 확인해 주세요.':p.diarization_status==='error'?'자동 화자 구분에 실패했습니다. 녹취는 저장되었으며 화자를 직접 지정할 수 있습니다.':'현재는 화자를 직접 지정할 수 있습니다. 자동 구분은 별도 로컬 모델 설정이 필요합니다.'}</div>
      <form id="speakers-form">${keys.map((key,i)=>`<div class="field"><label for="name-${i}">화자 ${i+1}</label><input id="name-${i}" data-speaker-name="${esc(key)}" value="${esc(p.speakers[key]||'')}" placeholder="예: 시장님, 질문자 1" maxlength="80"></div>`).join('')}<div class="row"><button type="button" class="btn" data-action="add-speaker">${icon('plus')}화자 추가</button><button class="btn primary" type="submit">이름 저장</button></div></form><p style="margin-top:18px">각 발언 위의 화자 메뉴에서 지정할 수 있습니다. 여러 사람이 겹쳐 말한 부분은 직접 확인해 주세요.</p>`;
  }
  return `<h3>확인한 기록으로, 다음 문서까지</h3><p>로컬 모델이 정리한 초안입니다. 원문과 사실관계를 확인한 뒤 사용하세요.</p><form id="draft-form" style="margin-top:20px"><div class="field"><label for="draft-kind">만들 결과물</label><select id="draft-kind">${Object.entries(draftNames).map(([key,value])=>`<option value="${key}">${value}</option>`).join('')}</select></div><div class="field" id="mayor-field" hidden><label for="mayor-speaker">시장님으로 지정할 화자</label><select id="mayor-speaker"><option value="">화자를 선택하세요</option>${speakerOptions()}</select></div><label class="check-label"><input type="checkbox" id="reviewed-only" checked>검토 완료로 표시한 발언만 사용</label><button class="btn primary" type="submit" ${p.status!=='completed'?'disabled':''}>${icon('spark')}로컬 AI로 생성</button></form>
    ${p.drafts.map(d=>`<div class="draft-card"><div class="row spread"><h3>${draftNames[d.kind]}</h3><span class="tag ${d.status==='error'?'red':d.status==='completed'?'green':'orange'}">${{queued:'대기 중',running:'생성 중',completed:'생성 완료',error:'생성 실패'}[d.status]}</span></div><small class="muted">${date(d.created_at)} · ${d.reviewed_only?'검토한 발언':'미검토 발언 포함'}</small>${d.stale?'<div class="notice">녹취 또는 참고정보가 변경되었습니다. 최신 내용으로 다시 생성해 주세요.</div>':''}${d.error?`<div class="notice error">${esc(d.error)}</div>`:''}
      ${d.content.map(s=>`<section class="draft-section"><h4>${esc(s.heading)}</h4><p>${esc(s.body)}</p>${s.segment_ids.map(id=>{const segment=p.segments.find(x=>x.id===id);return segment?`<button class="source-link" data-action="source" data-id="${id}">${icon('play')} ${time(segment.start)} 원문</button>`:'';}).join('')}</section>`).join('')}
      ${d.status==='completed'?`<div class="row" style="margin-top:12px"><button class="btn small" data-action="download-draft" data-id="${d.id}" data-format="txt" ${d.stale?'disabled':''}>TXT</button><button class="btn small" data-action="download-draft" data-id="${d.id}" data-format="pdf" ${d.stale?'disabled':''}>PDF</button></div>`:''}</div>`).join('')}`;
}
function renderDetail() {
  const p=state.project;if(!p)return;
  const reviewed=p.segments.filter(s=>s.reviewed).length;
  shell(`<section class="detail-heading"><button class="text-link" style="padding:0" data-action="library">${icon('back')}녹음 보관함</button><div class="row spread"><div><h1>${esc(p.title)} <button class="icon-btn" data-action="rename" aria-label="제목 변경">${icon('edit')}</button></h1><div class="meta"><span>${esc(p.kind)}</span><span>${date(p.created_at)}</span><span>${time(p.duration)}</span>${statusTag(p)}</div></div><div class="detail-actions">${busyStates.includes(p.status)?`<button class="btn" data-action="pause" ${p.status==='canceling'?'disabled':''}>${icon('pause')}일시 중지</button>`:p.status!=='completed'?`<button class="btn primary" data-action="transcribe">${icon('wave')}${p.next_chunk?'이어서 처리':'음성인식 시작'}</button>`:''}<button class="btn" data-action="export">${icon('download')}내보내기</button><button class="icon-btn" data-action="delete" aria-label="녹음 삭제">${icon('trash')}</button></div></div></section>
    ${busyStates.includes(p.status)||p.status==='paused'?`<div class="notice"><div class="row spread"><span>${esc(p.message)}</span><span>${Math.round(p.progress*100)}%</span></div><div class="progress-track" style="margin-top:9px"><span style="width:${p.progress*100}%"></span></div></div>`:''}
    ${p.error?`<div class="notice error">${esc(p.error)}</div>`:''}
    <div class="workspace"><section class="panel"><header class="panel-head"><h2>전체 녹취록 <small>${p.segments.length}개 발언</small></h2><small>${reviewed} / ${p.segments.length} 검토 완료</small></header><div class="transcript-tools"><input id="segment-search" aria-label="녹취 검색" placeholder="녹취 내용 검색" value="${esc(state.segmentSearch)}"><select id="segment-filter" aria-label="발언 필터"><option value="all" ${state.segmentFilter==='all'?'selected':''}>전체 발언</option><option value="review" ${state.segmentFilter==='review'?'selected':''}>미검토 발언</option><option value="flagged" ${state.segmentFilter==='flagged'?'selected':''}>확인 권장</option></select></div><div class="segments" id="segments">${renderSegments()}</div></section>
    <aside class="panel"><div class="side-tabs">${[['reference','사전 참고정보'],['speakers','화자 관리'],['drafts','발언·초안']].map(([key,label])=>`<button class="side-tab ${state.tab===key?'active':''}" data-action="side-tab" data-value="${key}">${label}</button>`).join('')}</div><div class="side-content">${renderSide()}</div></aside></div>`,true);
  bindDetailForms(); setupPlayer(); updatePlayback();
}
function bindDetailForms() {
  $('#reference-form')?.addEventListener('submit',async e=>{e.preventDefault();try{const result=await api(`/projects/${state.project.id}`,{method:'PATCH',body:{reference:$('#reference').value,terms:$('#terms').value}});Object.assign(state.project,result);referenceBuffers.delete(state.project.id);toast('참고정보를 저장했습니다. 기존 녹취는 변경하지 않습니다.');}catch(err){toast(err.message);}});
  $('#speakers-form')?.addEventListener('submit',async e=>{e.preventDefault();await saveSpeakers();});
  $('#draft-kind')?.addEventListener('change',e=>{$('#mayor-field').hidden=e.target.value!=='mayor';});
  $('#draft-form')?.addEventListener('submit',async e=>{
    e.preventDefault(); const button=$('button[type=submit]',e.target);button.disabled=true;
    try{await flushSaves();await api(`/projects/${state.project.id}/drafts`,{method:'POST',body:{kind:$('#draft-kind').value,reviewed_only:$('#reviewed-only').checked,speaker:$('#mayor-speaker').value||null}});await refreshDetail();toast('생성을 시작했습니다. 로컬 모델의 처리 시간은 PC에 따라 달라집니다.');}catch(err){toast(err.message);}finally{button.disabled=false;}
  });
}
async function saveSpeakers() {
  const speakers={...state.project.speakers};$$('[data-speaker-name]').forEach(input=>{if(input.value.trim())speakers[input.dataset.speakerName]=input.value.trim();});
  try{await api(`/projects/${state.project.id}`,{method:'PATCH',body:{speakers}});state.project.speakers=speakers;renderDetail();toast('화자 이름을 저장했습니다.');return true;}catch(err){toast(err.message);return false;}
}
async function saveSegment(id, changes) {
  const project=state.project;const segment=project?.segments.find(s=>s.id===id);if(!segment)return;
  // Serialize saves per segment so a blur and a review click cannot race on version.
  const previous=saves.get(id)||Promise.resolve();
  const promise=previous.catch(()=>{}).then(async()=>{
    const payload={text:segment.text,speaker:segment.speaker,reviewed:!!segment.reviewed,...changes,version:segment.version};
    const indicator=$(`#saved-${id}`);if(indicator)indicator.textContent='저장 중…';
    const response=await api(`/segments/${id}`,{method:'PATCH',body:payload});
    Object.assign(segment,payload,{version:response.version});
    failedSaves.delete(id);
    if(!$(`[data-segment="${id}"]`) || $(`[data-segment="${id}"]`).value===payload.text)dirtySegments.delete(id);
    if(indicator)indicator.textContent='저장됨';
  });
  saves.set(id,promise);
  try{await promise;}catch(err){failedSaves.set(id,changes);const indicator=$(`#saved-${id}`);if(indicator)indicator.textContent='저장 실패';toast(err.message);throw err;}finally{if(saves.get(id)===promise)saves.delete(id);}
}
async function flushSaves(){document.activeElement?.blur();await Promise.all([...saves.values()]);for(const [id,changes] of [...failedSaves])await saveSegment(id,changes);}
function setupPlayer() {
  const p=state.project;const audio=$('#audio');
  if(state.audioId!==p.id){audio.pause();audio.src=`/api/projects/${p.id}/audio`;state.audioId=p.id;state.repeat=null;}
  const peakMax=Math.max(...p.peaks,0.001);
  $('#player').className='player';
  $('#player').innerHTML=`<div class="player-top"><button class="icon-btn" data-action="skip" data-value="-5" aria-label="5초 뒤로">${icon('rewind')}</button><button class="play-button" id="play-button" data-action="play" aria-label="재생">${icon(audio.paused?'play':'pause')}</button><button class="icon-btn" data-action="skip" data-value="5" aria-label="5초 앞으로">${icon('forward')}</button><div class="player-time"><strong id="current-time">${time(audio.currentTime)}</strong> / ${time(p.duration)}</div><div class="waveform" id="waveform" title="눌러서 재생 위치 이동">${p.peaks.map((v,i)=>`<span data-peak="${i/p.peaks.length}" style="height:${Math.max(3,Math.sqrt(v/peakMax)*32)}px"></span>`).join('')}</div><button class="icon-btn player-repeat ${state.repeat?'active':''}" data-action="toggle-repeat" aria-label="구간 반복 해제" title="녹취 구간의 반복 버튼을 눌러 사용하세요">${icon('repeat')}</button><select class="player-speed" id="playback-speed" aria-label="재생 속도">${[.5,.75,1,1.25,1.5,2].map(n=>`<option value="${n}" ${audio.playbackRate===n?'selected':''}>${n}×</option>`).join('')}</select></div><input type="range" class="seek" id="seek" min="0" max="${p.duration}" step="0.1" value="${audio.currentTime}" aria-label="재생 위치"><div class="player-bottom"><span>${esc(p.filename)}${state.repeat?' · 구간 반복 중':''}</span><span>발언 시간을 누르면 해당 시점으로 이동합니다 · 원본 음성 재생</span></div>`;
  $('#seek').addEventListener('input',e=>{state.repeat=null;audio.currentTime=Number(e.target.value);});
  $('#playback-speed').addEventListener('change',e=>audio.playbackRate=Number(e.target.value));
  $('#waveform').addEventListener('click',e=>{const rect=e.currentTarget.getBoundingClientRect();state.repeat=null;audio.currentTime=(e.clientX-rect.left)/rect.width*p.duration;});
}
function updatePlayback() {
  const audio=$('#audio');if(state.page!=='detail')return;
  if(state.repeat && audio.currentTime>=state.repeat.end)audio.currentTime=state.repeat.start;
  if($('#current-time'))$('#current-time').textContent=time(audio.currentTime);
  if($('#seek'))$('#seek').value=audio.currentTime;
  $$('.segment').forEach(el=>el.classList.toggle('playing',audio.currentTime>=Number(el.dataset.start)&&audio.currentTime<Number(el.dataset.end)));
  $$('[data-peak]').forEach(el=>el.classList.toggle('past',Number(el.dataset.peak)<audio.currentTime/(state.project?.duration||1)));
  if($('#play-button')){$('#play-button').innerHTML=icon(audio.paused?'play':'pause');$('#play-button').setAttribute('aria-label',audio.paused?'재생':'일시 정지');}
}
async function seek(seconds, play=true){const audio=$('#audio');audio.currentTime=Number(seconds);if(play)try{await audio.play();}catch{toast('오디오 재생을 시작하지 못했습니다. 파일 형식을 확인해 주세요.');}updatePlayback();}
async function renderSettings() {
  const [settings,health]=await Promise.all([api('/settings'),api('/health')]);state.settings=settings;state.health=health;
  shell(`<section class="greeting"><div><div class="eyebrow">MADE FOR YOUR PC</div><h1>로컬 환경 설정</h1><p>모델을 한 번 준비하면, 녹음과 텍스트를 외부로 보내지 않고 처리합니다.</p></div><button class="btn" data-action="settings">${icon('checkCircle')}설치 상태 확인</button></section><div class="settings-grid"><section class="settings-box"><h2>설치 상태</h2>${[[health.ffmpeg,'오디오 변환 도구 (FFmpeg)'],[health.whisper_package,'음성인식 실행 패키지'],[health.whisper_model,'Whisper large-v3 모델 파일'],[health.ollama_online,'로컬 Ollama 연결'],[health.ollama_models.includes(settings.ollama_model),'선택한 문서 생성 모델']].map(([ok,label])=>`<div class="status-line"><span class="${ok?'good':'bad'}">${icon(ok?'checkCircle':'help')}</span>${label}<span class="spacer"></span><span class="tag ${ok?'green':'orange'}">${ok?'확인됨':'준비 필요'}</span></div>`).join('')}<div class="notice">파일 존재 확인은 실제 추론 성공을 뜻하지 않습니다. 짧은 녹음으로 먼저 실행을 확인해 주세요.</div><p class="small muted">데이터 저장 위치</p><code>${esc(health.data_dir)}</code><button class="btn" style="margin-top:20px" data-action="backup">${icon('download')}녹음·기록 전체 백업</button></section>
    <section class="settings-box"><h2>Windows에서 처음 시작하기</h2><p class="small muted">저장소의 설치 스크립트를 PowerShell에서 실행하세요.</p><code class="code-block">.\\scripts\\install.ps1
.\\.venv\\Scripts\\python.exe scripts\\download_model.py
ollama pull qwen3:8b
.\\start.bat</code><p class="small muted" style="margin-top:15px">Python 3.12, FFmpeg, Ollama와 NVIDIA 드라이버가 필요합니다. 자세한 설치·복구 방법은 함께 제공한 README.md를 확인해 주세요.</p><div class="notice">Whisper와 문서 생성 모델은 순서대로 실행합니다. 8GB 그래픽 메모리의 동시 점유를 줄이기 위한 구성입니다.</div></section>
    <section class="settings-box full"><h2>모델 실행 설정</h2><form id="settings-form"><div class="field"><label for="setting-whisper_model">Whisper 모델 폴더</label><input id="setting-whisper_model" value="${esc(settings.whisper_model)}" required><small>model.bin이 들어 있는 로컬 폴더. 앱에서 자동으로 다운로드하지 않습니다.</small></div><div class="field-row"><div class="field"><label for="setting-device">실행 장치</label><select id="setting-device"><option value="cuda" ${settings.device==='cuda'?'selected':''}>NVIDIA GPU (권장)</option><option value="cpu" ${settings.device==='cpu'?'selected':''}>CPU</option></select></div><div class="field"><label for="setting-compute_type">연산 방식</label><select id="setting-compute_type">${['float16','float32','int8'].map(v=>`<option ${settings.compute_type===v?'selected':''}>${v}</option>`).join('')}</select><small>GPU: float16 우선 / CPU: float32 또는 int8</small></div></div><div class="field"><label for="setting-ollama_model">Ollama 문서 생성 모델</label><input id="setting-ollama_model" value="${esc(settings.ollama_model)}" required><small>연결은 이 PC의 127.0.0.1:11434로 제한됩니다. 설치된 모델: ${esc(health.ollama_models.join(', ')||'없음')}</small></div><div class="field"><label for="setting-diarization_model">자동 화자 구분 모델 (선택·고급)</label><input id="setting-diarization_model" value="${esc(settings.diarization_model)}" placeholder="설치한 pyannote 로컬 모델 경로"><small>별도 패키지와 모든 가중치를 로컬에 준비해야 합니다. 비워 두면 화자를 직접 지정합니다.</small></div><button class="btn primary" type="submit">${icon('save')}설정 저장</button></form></section></div>`);
  $('#settings-form').addEventListener('submit',async e=>{e.preventDefault();const payload={};Object.keys(settings).forEach(key=>{const input=$(`#setting-${key}`);if(input)payload[key]=input.value;});try{await api('/settings',{method:'PUT',body:payload});toast('설정을 저장했습니다.');await renderSettings();}catch(err){toast(err.message);}});
}
async function renderGuide() {
  if(!state.prompt)state.prompt=(await api('/reference-prompt')).text;
  shell(`<section class="greeting"><div><div class="eyebrow">A LITTLE PREPARATION, A BETTER RECORD</div><h1>기록을 시작하는 방법</h1><p>녹음은 그대로 보존하고, 확인할 수 있는 기록을 만듭니다.</p></div></section><div class="help-page"><section class="help-card"><h2>01. 사전 자료는 ChatGPT에서 준비해 주세요</h2><ol><li>ChatGPT의 새 대화에 행사 계획서·참석자·사업 설명자료를 첨부하세요.</li><li>아래 프롬프트를 함께 보내세요. HWP를 읽지 못하면 PDF로 저장해 첨부하세요.</li><li>답변의 인명·사업명·숫자와 확인 필요 사항을 검토하세요.</li><li>분석 결과 전체를 녹취 작업실의 ‘사전 참고정보’에 붙여넣으세요.</li><li>8번 구역의 용어를 가져와 확인하고 저장한 뒤 음성인식을 시작하세요.</li></ol><div class="notice">이 단계에서는 사용자가 자료를 ChatGPT에 직접 제공합니다. 로컬 앱은 ChatGPT 계정에 접속하거나 자료를 자동 전송하지 않습니다.</div><div class="row spread" style="margin:20px 0 10px"><h3>사전 자료 분석 프롬프트</h3><button class="btn small" data-action="copy-prompt">${icon('copy')}프롬프트 복사</button></div><textarea readonly aria-label="ChatGPT 사전 자료 분석 프롬프트">${esc(state.prompt)}</textarea></section><section class="help-card"><h2>02. 듣고, 고치고, 확인해 주세요</h2><p>녹음 파일을 추가하고 음성인식을 시작하세요. 문장 옆 시간을 누르면 해당 음성을 들을 수 있습니다. 텍스트는 수정 후 다른 곳을 누르면 자동 저장되며, 확인한 발언에 ‘검토 완료’를 표시하세요. 자동 녹취 원문과 수정 이력은 별도로 남습니다.</p><p style="margin-top:12px">정확도가 우선이라면 녹음기의 무손실 녹음 모드를 권장합니다. 이미 있는 MP3는 그대로 사용하세요. WAV로 변환해도 손실된 정보가 복원되지는 않습니다. 인식의 불확실성 표시는 검토 안내이며 정확도 보증이 아닙니다.</p></section><section class="help-card"><h2>03. 원문에 연결된 발언과 초안을 만드세요</h2><p>화자 관리에서 시장님 이름을 지정하고, 발언·초안에서 결과물을 선택하세요. 기본값은 검토 완료 발언만 사용합니다. 생성된 내용의 시간 링크를 눌러 원문을 다시 확인할 수 있습니다. 긴 녹음의 문서는 구간별로 생성되므로 최종 문서의 연결과 중복도 검토해 주세요.</p><p style="margin-top:12px">전체 녹취는 자동 원문·편집본·검토 완료 발언 중 선택해 TXT 또는 한글 글꼴이 포함된 PDF로 내보낼 수 있습니다.</p></section><section class="help-card"><h2>04. 내 기록을 오래 보관하세요</h2><p>환경 설정에서 전체 백업 ZIP을 다운로드해 다른 디스크에도 보관하세요. 원본 녹음·녹취·참고정보·수정 이력이 포함됩니다. 실행 중인 모델과 설치 파일은 백업에 포함되지 않습니다. 복원 방법은 README.md에 안내되어 있습니다.</p></section></div>`);
}
async function exportModal() {
  await flushSaves();
  showModal('녹취록 내보내기',`<form id="export-form"><div class="field"><label for="export-mode">내보낼 내용</label><select id="export-mode"><option value="edited">편집 녹취록 (미검토 포함)</option><option value="reviewed">검토 완료 발언만</option><option value="original">자동 녹취 원문</option></select></div><div class="field"><label for="export-format">파일 형식</label><select id="export-format"><option value="txt">TXT · UTF-8 텍스트</option><option value="pdf">PDF · 한글 글꼴 포함</option></select></div><p class="muted small">화자와 발언 시간이 함께 표시됩니다. AI 초안은 ‘발언·초안’ 탭에서 별도로 내보낼 수 있습니다.</p><div class="modal-footer"><button type="button" class="btn" data-action="close-modal">취소</button><button type="submit" class="btn primary">${icon('download')}내보내기</button></div></form>`);
  $('#export-form').addEventListener('submit',async e=>{e.preventDefault();try{await download(`/projects/${state.project.id}/export?format=${$('#export-format').value}&mode=${$('#export-mode').value}`,`${state.project.title}.${$('#export-format').value}`);$('#modal').close();}catch(err){toast(err.message);}});
}
async function download(url, filename) {
  const response=await fetch('/api'+url);
  if(!response.ok){const payload=await response.json();throw new Error(payload.detail||'내보내기에 실패했습니다.');}
  const blob=await response.blob();const href=URL.createObjectURL(blob);const link=document.createElement('a');link.href=href;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(href),10000);
}
async function refreshProjects(){state.projects=await api('/projects');}
async function refreshDetail(){const id=state.project?.id;if(!id)return;const project=await api(`/projects/${id}`);if(state.project?.id===id){state.project=project;if(state.page==='detail'){const scroll=$('#segments')?.scrollTop||0;renderDetail();if($('#segments'))$('#segments').scrollTop=scroll;}}}
async function route() {
  const hash=location.hash.slice(1)||'library';
  try {
    await flushSaves();
    await refreshProjects();
    if(hash.startsWith('project/')){const id=hash.split('/')[1];state.page='detail';state.project=await api(`/projects/${encodeURIComponent(id)}`);state.segmentSearch='';state.segmentFilter='all';renderDetail();}
    else{state.page=['settings','guide'].includes(hash)?hash:'library';$('#audio').pause();if(state.page==='settings')await renderSettings();else if(state.page==='guide')await renderGuide();else renderLibrary();}
  }catch(err){if(failedSaves.size){history.replaceState(null,'',`#project/${state.project.id}`);toast('수정 내용을 저장하지 못해 현재 화면을 유지합니다. 연결을 확인해 주세요.');return;}shell(`<div class="error-page"><h2>기록실을 열 수 없습니다</h2><p class="muted" style="margin:20px">${esc(err.message)}</p><button class="btn" data-action="library">보관함으로 돌아가기</button></div>`);}
}
function go(page){if(location.hash===`#${page}`)route();else location.hash=page;}
document.addEventListener('click',async e=>{
  const button=e.target.closest('[data-action]');if(!button||button.disabled)return;
  const action=button.dataset.action;
  try{
    if(action==='close-modal'){$('#modal').close();return;}
    if(action==='library'){state.filter='전체';go('library');return;}
    if(action==='reviewed-library'){state.filter='검토 완료';go('library');return;}
    if(action==='settings'||action==='guide'){go(action);return;}
    if(action==='upload'){openUpload();return;}
    if(action==='copy-prompt'){await copyPrompt();return;}
    if(action==='filter'){state.filter=button.dataset.value;renderLibrary();return;}
    if(action==='open-project'){go(`project/${button.dataset.id}`);return;}
    if(action==='side-tab'){await flushSaves();state.tab=button.dataset.value;renderDetail();return;}
    if(action==='extract-terms'){const match=$('#reference').value.match(/\[8\.\s*음성인식용 압축 용어 목록\]\s*([^\[]*)/);if(!match){toast('8번 구역을 찾지 못했습니다. 용어를 직접 입력해 주세요.');return;}$('#terms').value=match[1].trim().replace(/^[-\s`]+/,'').replace(/\n/g,', ').slice(0,400);referenceBuffers.set(state.project.id,{reference:$('#reference').value,terms:$('#terms').value});toast('용어를 가져왔습니다. 확인한 뒤 저장해 주세요.');return;}
    if(action==='transcribe'){await flushSaves();const buffer=$('#reference-form')?{reference:$('#reference').value,terms:$('#terms').value}:referenceBuffers.get(state.project.id);if(buffer){await api(`/projects/${state.project.id}`,{method:'PATCH',body:buffer});referenceBuffers.delete(state.project.id);}await api(`/projects/${state.project.id}/transcribe`,{method:'POST'});await refreshDetail();return;}
    if(action==='pause'){await api(`/projects/${state.project.id}/pause`,{method:'POST'});await refreshDetail();return;}
    if(action==='seek'){state.repeat=null;await seek(button.dataset.time);return;}
    if(action==='play'){const audio=$('#audio');if(audio.paused)await audio.play();else audio.pause();updatePlayback();return;}
    if(action==='skip'){state.repeat=null;await seek(Math.min(state.project.duration,Math.max(0,$('#audio').currentTime+Number(button.dataset.value))),false);return;}
    if(action==='repeat-segment'){const segment=state.project.segments.find(s=>s.id===Number(button.dataset.id));state.repeat={start:segment.start,end:segment.end};setupPlayer();await seek(segment.start);return;}
    if(action==='toggle-repeat'){state.repeat=null;setupPlayer();return;}
    if(action==='review'){const id=Number(button.dataset.id);const s=state.project.segments.find(x=>x.id===id);const text=$(`[data-segment="${id}"]`).value;const reviewed=!button.classList.contains('done');await saveSegment(id,{reviewed,text});button.classList.toggle('done',!!s.reviewed);button.innerHTML=icon('check')+(s.reviewed?'검토 완료':'검토 완료 표시');return;}
    if(action==='history'){const entries=await api(`/segments/${button.dataset.id}/history`);showModal('발언 수정 이력',entries.length?entries.map(entry=>`<div class="history-entry"><time>${new Date(entry.created_at).toLocaleString('ko-KR')}</time><p>${esc(entry.text)}</p><small class="muted">${entry.reviewed?'검토 완료 상태':'미검토 상태'}</small></div>`).join(''):'<p class="muted">아직 수정 이력이 없습니다.</p>');return;}
    if(action==='add-speaker'){await saveSpeakers();const key=`speaker_${crypto.randomUUID().slice(0,8)}`;state.project.speakers[key]='새 화자';renderDetail();return;}
    if(action==='source'){state.segmentFilter='all';state.segmentSearch='';renderDetail();const segment=state.project.segments.find(s=>s.id===Number(button.dataset.id));$(`#segment-${segment.id}`)?.scrollIntoView({behavior:'smooth',block:'center'});await seek(segment.start);return;}
    if(action==='export'){await exportModal();return;}
    if(action==='download-draft'){await flushSaves();await download(`/projects/${state.project.id}/export?format=${button.dataset.format}&draft=${button.dataset.id}`,`${state.project.title}-초안.${button.dataset.format}`);return;}
    if(action==='backup'){button.disabled=true;toast('원본 녹음과 기록을 백업하고 있습니다.');try{await download('/backup',`목소리기록실-백업-${new Date().toISOString().slice(0,10)}.zip`);toast('백업 파일을 내려받았습니다.');}finally{button.disabled=false;}return;}
    if(action==='rename'){showModal('기록 제목 변경',`<form id="rename-form"><div class="field"><label for="rename-title">제목</label><input id="rename-title" value="${esc(state.project.title)}" maxlength="160" required></div><div class="modal-footer"><button class="btn primary" type="submit">저장</button></div></form>`);$('#rename-form').addEventListener('submit',async event=>{event.preventDefault();try{await api(`/projects/${state.project.id}`,{method:'PATCH',body:{title:$('#rename-title').value}});$('#modal').close();await refreshDetail();}catch(err){toast(err.message);}});return;}
    if(action==='delete'){showModal('이 녹음을 삭제할까요?',`<p class="confirm-description">${esc(state.project.title)}\n원본 파일, 녹취, 참고정보와 수정 이력이 함께 삭제됩니다. 필요한 기록은 먼저 백업해 주세요.</p><div class="modal-footer"><button class="btn" data-action="close-modal">보관하기</button><button class="btn danger" data-action="confirm-delete">녹음과 기록 삭제</button></div>`);return;}
    if(action==='confirm-delete'){await api(`/projects/${state.project.id}`,{method:'DELETE'});$('#modal').close();$('#audio').pause();state.audioId=null;go('library');toast('녹음과 기록을 삭제했습니다.');}
  }catch(err){toast(err.message);}
});
document.addEventListener('input',e=>{
  if(e.target.id==='library-search'){const input=e.target;const position=input.selectionStart;state.search=input.value;renderLibrary();$('#library-search').focus();$('#library-search').setSelectionRange(position,position);}
  if(e.target.id==='segment-search'){state.segmentSearch=e.target.value;$('#segments').innerHTML=renderSegments();}
  if(['reference','terms'].includes(e.target.id))referenceBuffers.set(state.project.id,{reference:$('#reference').value,terms:$('#terms').value});
  if(e.target.dataset.segment){dirtySegments.add(Number(e.target.dataset.segment));const indicator=$(`#saved-${e.target.dataset.segment}`);if(indicator)indicator.textContent='편집 중';const review=$(`[data-action="review"][data-id="${e.target.dataset.segment}"]`);if(review){review.classList.remove('done');review.innerHTML=icon('check')+'검토 완료 표시';}}
});
document.addEventListener('change',e=>{
  if(e.target.dataset.segment){const id=Number(e.target.dataset.segment);saveSegment(id,{text:e.target.value,reviewed:false}).catch(()=>{});}
  if(e.target.dataset.speaker){const id=Number(e.target.dataset.speaker);const review=$(`[data-action="review"][data-id="${id}"]`);if(review){review.classList.remove('done');review.innerHTML=icon('check')+'검토 완료 표시';}saveSegment(id,{speaker:e.target.value,reviewed:false}).catch(()=>{});}
  if(e.target.id==='segment-filter'){state.segmentFilter=e.target.value;$('#segments').innerHTML=renderSegments();}
});
$('#audio').addEventListener('timeupdate',updatePlayback);$('#audio').addEventListener('pause',updatePlayback);$('#audio').addEventListener('play',updatePlayback);
$('#audio').addEventListener('error',()=>{if(state.audioId)toast('이 브라우저에서 원본을 재생하지 못했습니다. MP3 또는 WAV 파일을 사용해 주세요.');});
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload',e=>{if(saves.size||dirtySegments.size||failedSaves.size||referenceBuffers.size){e.preventDefault();e.returnValue='';}});
setInterval(async()=>{
  if(pollBusy||$('#modal').open||saves.size||dirtySegments.size||failedSaves.size||document.activeElement?.matches('input,textarea,select')||!$('#audio').paused)return;
  const active=state.page==='detail'&&(busyStates.includes(state.project?.status)||state.project?.drafts.some(d=>['queued','running'].includes(d.status)));
  if(!active)return;pollBusy=true;try{await refreshDetail();}catch{}finally{pollBusy=false;}
},3000);
route();
