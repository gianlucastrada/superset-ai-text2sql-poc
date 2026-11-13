/* Caricato in ogni pagina di Superset (tail_js_custom_extra.html).
   - Pulsante flottante "AI Assistant" verso /ai/
   - In SQL Lab: pannello "Text-to-SQL" che genera la query e la mette nell'editor. */
(function () {
  'use strict';
  if (window.__supersetAi) return;
  window.__supersetAi = true;
  if (location.pathname.indexOf('/login') === 0) return;

  var csrf = null;
  var info = null;

  async function api(metodo, url, corpo) {
    var headers = { Accept: 'application/json' };
    if (corpo !== undefined) headers['Content-Type'] = 'application/json';
    if (metodo !== 'GET') {
      if (!csrf) {
        var t = await fetch('/api/v1/security/csrf_token/', { credentials: 'same-origin' });
        csrf = (await t.json()).result;
      }
      headers['X-CSRFToken'] = csrf;
    }
    var r = await fetch(url, { method: metodo, headers: headers, credentials: 'same-origin', body: corpo === undefined ? undefined : JSON.stringify(corpo) });
    var j = null;
    try { j = await r.json(); } catch (e) { /* non JSON */ }
    if (!r.ok) throw new Error((j && (j.errore || j.message)) || ('HTTP ' + r.status));
    return j;
  }

  // ------------------------------------------------------------------ stile
  var css = document.createElement('style');
  css.textContent = [
    '.sai-fab{position:fixed;right:18px;bottom:18px;z-index:2000;display:flex;gap:8px}',
    '.sai-btn{border:0;border-radius:20px;padding:8px 14px;background:#20a7c9;color:#fff;font:13px/1.2 Inter,Segoe UI,Arial,sans-serif;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.25);text-decoration:none}',
    '.sai-btn.sec{background:#fff;color:#1987a3;border:1px solid #20a7c9;box-shadow:none;border-radius:6px;padding:6px 10px}',
    '.sai-btn:disabled{opacity:.5;cursor:wait}',
    '.sai-pan{position:fixed;right:18px;bottom:64px;z-index:2001;width:440px;max-width:calc(100vw - 36px);background:#fff;color:#1f2933;border:1px solid #d9e2ec;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.25);padding:14px;font:13px/1.4 Inter,Segoe UI,Arial,sans-serif;display:none}',
    '.sai-pan h3{margin:0 0 6px;font-size:15px}',
    '.sai-pan p{margin:0 0 8px;color:#616e7c}',
    '.sai-pan textarea{width:100%;box-sizing:border-box;border:1px solid #d9e2ec;border-radius:6px;padding:8px;font:inherit;resize:vertical}',
    '.sai-pan pre{background:#f5f7fa;border:1px solid #d9e2ec;border-radius:6px;padding:8px;max-height:220px;overflow:auto;white-space:pre-wrap;font:12px/1.4 Consolas,monospace;margin:8px 0}',
    '.sai-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center}',
    '.sai-msg{margin-top:8px;white-space:pre-wrap}',
    '.sai-err{color:#c0392b}',
    '.sai-dark.sai-pan{background:#1c1c1c;color:#e6e8eb;border-color:#333a40}',
    '.sai-dark.sai-pan p{color:#9aa5b1}',
    '.sai-dark.sai-pan textarea{background:#161616;color:#e6e8eb;border-color:#333a40}',
    '.sai-dark.sai-pan pre{background:#161616;color:#e6e8eb;border-color:#333a40}',
    '.sai-dark.sai-pan .sai-err{color:#ff8a80}',
    '.sai-dark .sai-btn.sec{background:#1c1c1c;color:#5cc8e3}',
  ].join('\n');
  document.head.appendChild(css);

  // Tema scuro: Superset salva la modalita' in localStorage ('default' | 'dark' | 'system')
  function scuro() {
    try {
      var m = localStorage.getItem('superset-theme-mode');
      if (m) { try { m = JSON.parse(m); } catch (e) {} }
      return m === 'dark' || ((!m || m === 'system') && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    } catch (e) { return false; }
  }
  function aggiornaTema() { pan.classList.toggle('sai-dark', scuro()); }

  // ------------------------------------------------------------------ pulsanti
  var fab = document.createElement('div');
  fab.className = 'sai-fab';
  var bSql = document.createElement('button');
  bSql.className = 'sai-btn';
  bSql.type = 'button';
  bSql.textContent = 'Text-to-SQL';
  var bAi = document.createElement('a');
  bAi.className = 'sai-btn';
  bAi.href = '/ai/';
  bAi.textContent = 'AI Assistant';
  fab.appendChild(bSql);
  fab.appendChild(bAi);

  // ------------------------------------------------------------------ pannello SQL Lab
  var pan = document.createElement('div');
  pan.className = 'sai-pan';
  pan.innerHTML =
    '<h3>Text-to-SQL</h3>' +
    '<p class="sai-db">Descrivi la query in italiano.</p>' +
    '<textarea rows="3" class="sai-q" placeholder="Es. fatturato per categoria nel 2026, escludendo gli annullati"></textarea>' +
    '<div class="sai-row"><button type="button" class="sai-btn sai-gen">Genera SQL</button><span class="sai-t"></span></div>' +
    '<div class="sai-msg"></div>' +
    '<pre class="sai-sql" style="display:none"></pre>' +
    '<div class="sai-row sai-azioni" style="display:none">' +
    '<button type="button" class="sai-btn sec sai-nuova">Apri in nuova scheda</button>' +
    '<button type="button" class="sai-btn sec sai-ins">Inserisci nell\'editor</button>' +
    '<button type="button" class="sai-btn sec sai-copia">Copia</button></div>';

  function q(sel) { return pan.querySelector(sel); }
  var sqlCorrente = '';

  function msg(testo, errore) {
    var m = q('.sai-msg');
    m.textContent = testo || '';
    m.className = 'sai-msg' + (errore ? ' sai-err' : '');
  }

  async function genera() {
    var domanda = q('.sai-q').value.trim();
    if (!domanda) { msg('Scrivi cosa vuoi estrarre.', true); return; }
    var bottone = q('.sai-gen');
    bottone.disabled = true;
    q('.sai-sql').style.display = 'none';
    q('.sai-azioni').style.display = 'none';
    var inizio = Date.now();
    var timer = setInterval(function () { q('.sai-t').textContent = Math.round((Date.now() - inizio) / 1000) + ' s'; }, 500);
    msg('Il modello sta scrivendo la query...');
    try {
      var r = await api('POST', '/ai/api/sql', { domanda: domanda, esegui: false });
      sqlCorrente = r.sql || '';
      q('.sai-sql').textContent = sqlCorrente;
      q('.sai-sql').style.display = 'block';
      q('.sai-azioni').style.display = 'flex';
      if (r.errore_sql) msg('Attenzione, la query non funziona ancora: ' + r.errore_sql, true);
      else if (r.avviso) msg('Attenzione: ' + r.avviso, true);
      else msg((r.spiegazione || '') + (r.tentativi > 1 ? ' (corretta automaticamente)' : ''));
    } catch (e) {
      msg(e.message, true);
    } finally {
      clearInterval(timer);
      bottone.disabled = false;
    }
  }

  // Editor Ace di SQL Lab: prende quello visibile piu' grande (non quello dei parametri)
  function editorSql() {
    var els = Array.prototype.slice.call(document.querySelectorAll('.ace_editor')).filter(function (e) {
      return e.offsetParent !== null && e.env && e.env.editor;
    });
    els.sort(function (a, b) { return b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight; });
    return els.length ? els[0].env.editor : null;
  }

  function inserisci() {
    var ed = editorSql();
    if (!ed) { msg('Editor non trovato: uso "Apri in nuova scheda".', true); apriNuova(); return; }
    // Accoda la query separandola con ';' e la seleziona: SQL Lab esegue solo il testo selezionato
    var esistente = ed.getValue().replace(/\s+$/, '');
    var prima = esistente ? esistente + (/;$/.test(esistente) ? '' : ';') + '\n\n' : '';
    var nuova = sqlCorrente.replace(/\s*;?\s*$/, '') + ';';
    ed.setValue(prima + nuova, 1);
    var righePrima = prima ? prima.split('\n').length - 1 : 0;
    var righeNuova = nuova.split('\n');
    ed.focus();
    ed.gotoLine(righePrima + 1, 0, false);
    ed.selection.selectTo(righePrima + righeNuova.length - 1, righeNuova[righeNuova.length - 1].length);
    msg('Query inserita e selezionata: premi Run per eseguire solo quella. Controlla che in alto sia selezionato il database "' + (info ? info.database_nome : '') + '".');
  }

  async function apriNuova() {
    if (!info) info = await api('GET', '/ai/api/info');
    var p = new URLSearchParams({ dbid: String(info.database_id), schema: info.schema, sql: sqlCorrente, name: 'AI: ' + q('.sai-q').value.trim().slice(0, 40) });
    location.href = '/sqllab/?' + p.toString();
  }

  bSql.addEventListener('click', async function () {
    aggiornaTema();
    var aperto = pan.style.display === 'block';
    pan.style.display = aperto ? 'none' : 'block';
    if (!aperto) {
      q('.sai-q').focus();
      try {
        if (!info) info = await api('GET', '/ai/api/info');
        q('.sai-db').textContent = 'Database: ' + info.database_nome + ' - modello ' + info.modello + '. Descrivi la query in italiano.';
      } catch (e) { /* mostrato alla generazione */ }
    }
  });
  q('.sai-gen').addEventListener('click', genera);
  q('.sai-q').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) genera(); });
  q('.sai-nuova').addEventListener('click', function () { apriNuova().catch(function (e) { msg(e.message, true); }); });
  q('.sai-ins').addEventListener('click', inserisci);
  q('.sai-copia').addEventListener('click', function () { navigator.clipboard.writeText(sqlCorrente); msg('Copiata negli appunti.'); });

  function monta() {
    if (!document.body) return;
    document.body.appendChild(fab);
    document.body.appendChild(pan);
    // Superset e' una single page app: mostro "Text-to-SQL" solo quando si e' in SQL Lab
    setInterval(function () {
      var inSqlLab = location.pathname.indexOf('/sqllab') === 0;
      bSql.style.display = inSqlLab ? '' : 'none';
      if (!inSqlLab) pan.style.display = 'none';
    }, 700);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', monta);
  else monta();
})();
