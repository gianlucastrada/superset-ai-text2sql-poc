/* Pagina "AI Assistant": Text-to-SQL e dashboard al volo (estensione superset_ai). */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var csrf = null;
  var info = null;

  // ------------------------------------------------------------------ chiamate HTTP
  async function tokenCsrf() {
    if (!csrf) {
      var r = await fetch('/api/v1/security/csrf_token/', { credentials: 'same-origin' });
      if (!r.ok) throw new Error('Impossibile ottenere il token CSRF (sessione scaduta?)');
      csrf = (await r.json()).result;
    }
    return csrf;
  }

  async function api(metodo, url, corpo) {
    var headers = { Accept: 'application/json' };
    if (corpo !== undefined) headers['Content-Type'] = 'application/json';
    if (metodo !== 'GET') headers['X-CSRFToken'] = await tokenCsrf();
    var r = await fetch(url, {
      method: metodo, headers: headers, credentials: 'same-origin',
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
    var j = null;
    try { j = await r.json(); } catch (e) { /* risposta non JSON */ }
    if (!r.ok) {
      var m = j && (j.errore || j.message || j.errors);
      if (m && typeof m !== 'string') m = JSON.stringify(m);
      throw new Error(m || ('HTTP ' + r.status));
    }
    return j;
  }

  // Ricerca tramite le API di Superset (filtri in formato rison)
  function rison(v) {
    return typeof v === 'number' ? String(v) : "'" + String(v).replace(/!/g, '!!').replace(/'/g, "!'") + "'";
  }
  async function cerca(percorso, filtri, colonne) {
    var q = '(filters:!(' + filtri.map(function (f) {
      return '(col:' + f[0] + ',opr:' + f[1] + ',value:' + rison(f[2]) + ')';
    }).join(',') + '),page_size:500' + (colonne ? ',columns:!(' + colonne.join(',') + ')' : '') + ')';
    var r = await api('GET', percorso + '?q=' + encodeURIComponent(q));
    return r.result || [];
  }
  // Hash stabile (cyrb53) della SQL: stessa query = stesso dataset riutilizzabile
  function hash(testo) {
    var h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (var i = 0; i < testo.length; i++) {
      var c = testo.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 2654435761);
      h2 = Math.imul(h2 ^ c, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
  }

  async function caricaInfo() {
    if (!info) info = await api('GET', '/ai/api/info');
    return info;
  }

  // ------------------------------------------------------------------ interfaccia
  function messaggio(el, testo, tipo) {
    el.className = 'msg ' + (tipo || 'info');
    el.textContent = testo;
  }
  function nascondi(el) { el.className = 'msg'; el.textContent = ''; }

  function tabella(contenitore, ris) {
    contenitore.textContent = '';
    if (!ris || !ris.colonne) return;
    var t = document.createElement('table');
    var th = t.createTHead().insertRow();
    ris.colonne.forEach(function (c) {
      var cella = document.createElement('th'); cella.textContent = c; th.appendChild(cella);
    });
    var tb = t.createTBody();
    ris.righe.forEach(function (riga) {
      var tr = tb.insertRow();
      riga.forEach(function (v, i) {
        var td = tr.insertCell();
        if (ris.tipi[i] === 'numerico' && typeof v === 'number') {
          td.className = 'num';
          td.textContent = v.toLocaleString('it-IT', { maximumFractionDigits: 2 });
        } else {
          td.textContent = v === null ? '' : String(v);
        }
      });
    });
    contenitore.appendChild(t);
  }

  function cronometro(el) {
    var inizio = Date.now();
    var h = setInterval(function () {
      el.textContent = 'In corso... ' + Math.round((Date.now() - inizio) / 1000) + ' s';
    }, 500);
    return function () {
      clearInterval(h);
      el.textContent = 'Completato in ' + Math.round((Date.now() - inizio) / 1000) + ' s';
    };
  }

  function urlSqlLab(sql, nome) {
    var p = new URLSearchParams({ dbid: String(info.database_id), schema: info.schema, sql: sql, name: nome || 'AI' });
    return '/sqllab/?' + p.toString();
  }

  // ------------------------------------------------------------------ Domanda -> SQL
  async function generaSql() {
    var domanda = $('domanda').value.trim();
    if (!domanda) { messaggio($('msgSql'), 'Scrivi una domanda.', 'err'); return; }
    $('btnSql').disabled = true;
    nascondi($('msgSql'));
    var fine = cronometro($('tempoSql'));
    messaggio($('msgSql'), 'Il modello sta scrivendo la query (la prima richiesta puo\' richiedere piu\' tempo mentre il modello viene caricato)...');
    try {
      var r = await api('POST', '/ai/api/sql', { domanda: domanda, esegui: true });
      $('bloccoSql').classList.remove('nascosto');
      $('sql').value = r.sql || '';
      if (r.errore_sql) {
        messaggio($('msgSql'), 'La query generata non funziona: ' + r.errore_sql + '\nPuoi correggerla a mano e premere "Riesegui SQL".', 'err');
        $('tabella').textContent = '';
      } else {
        var ris = r.risultato;
        messaggio($('msgSql'), (r.spiegazione || '') + '\n' + ris.righe.length + (ris.troncato ? '+' : '') + ' righe in ' + ris.ms + ' ms' + (r.tentativi > 1 && !r.avviso ? ' (query corretta automaticamente)' : '') +
          (r.avviso ? '\nATTENZIONE, il risultato potrebbe non rispondere alla domanda: ' + r.avviso : ''), r.avviso ? 'err' : 'ok');
        tabella($('tabella'), ris);
      }
    } catch (e) {
      messaggio($('msgSql'), e.message, 'err');
    } finally {
      fine();
      $('btnSql').disabled = false;
    }
  }

  async function rieseguiSql() {
    $('btnEsegui').disabled = true;
    try {
      var r = await api('POST', '/ai/api/esegui', { sql: $('sql').value });
      messaggio($('msgSql'), r.risultato.righe.length + (r.risultato.troncato ? '+' : '') + ' righe in ' + r.risultato.ms + ' ms', 'ok');
      tabella($('tabella'), r.risultato);
    } catch (e) {
      messaggio($('msgSql'), e.message, 'err');
    } finally {
      $('btnEsegui').disabled = false;
    }
  }

  async function apriSqlLab() {
    await caricaInfo();
    if (!info.database_id) { messaggio($('msgSql'), 'Database "' + info.database_nome + '" non trovato in Superset.', 'err'); return; }
    window.open(urlSqlLab($('sql').value, 'AI: ' + $('domanda').value.slice(0, 40)), '_blank');
  }

  // ------------------------------------------------------------------ Dashboard al volo
  function slug(s) {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40);
  }

  function metrica(colonna) {
    return {
      expressionType: 'SQL',
      sqlExpression: 'SUM("' + colonna.replace(/"/g, '""') + '")',
      label: colonna,
      optionName: 'metric_' + slug(colonna),
    };
  }

  // form_data di Superset per ogni tipo di grafico
  function formData(g, datasetId) {
    var base = { datasource: datasetId + '__table', row_limit: 1000 };
    var m = g.y ? metrica(g.y) : null;
    switch (g.tipo) {
      case 'big_number':
        return Object.assign(base, { viz_type: 'big_number_total', metric: m, subheader: '' });
      case 'bar':
        return Object.assign(base, {
          viz_type: 'echarts_timeseries_bar', x_axis: g.x, metrics: [m], groupby: [],
          x_axis_sort: m.label, x_axis_sort_asc: false, row_limit: 50,
          show_legend: false, show_value: true, orientation: 'vertical', xAxisLabelRotation: 45,
        });
      case 'line':
        return Object.assign(base, {
          viz_type: 'echarts_timeseries_line', x_axis: g.x, time_grain_sqla: 'P1M',
          metrics: [m], groupby: [], show_legend: false, markerEnabled: true,
        });
      case 'pie':
        return Object.assign(base, {
          viz_type: 'pie', groupby: [g.x], metric: m, row_limit: 25,
          show_labels: true, label_type: 'key_percent', show_legend: true,
        });
      default:
        return Object.assign(base, { viz_type: 'table', query_mode: 'raw', all_columns: g.colonne, order_by_cols: [] });
    }
  }

  // Disposizione: KPI in una riga, grafici a coppie, tabelle a tutta larghezza
  function layout(titolo, grafici) {
    var pos = {
      DASHBOARD_VERSION_KEY: 'v2',
      ROOT_ID: { type: 'ROOT', id: 'ROOT_ID', children: ['GRID_ID'] },
      GRID_ID: { type: 'GRID', id: 'GRID_ID', children: [], parents: ['ROOT_ID'] },
      HEADER_ID: { id: 'HEADER_ID', type: 'HEADER', meta: { text: titolo } },
    };
    var nRiga = 0;
    function riga(elementi) {
      nRiga += 1;
      var idRiga = 'ROW-ai-' + nRiga;
      pos[idRiga] = { type: 'ROW', id: idRiga, children: [], parents: ['ROOT_ID', 'GRID_ID'], meta: { background: 'BACKGROUND_TRANSPARENT' } };
      pos.GRID_ID.children.push(idRiga);
      elementi.forEach(function (e) {
        var idGraf = 'CHART-ai-' + e.id;
        pos[idGraf] = {
          type: 'CHART', id: idGraf, children: [], parents: ['ROOT_ID', 'GRID_ID', idRiga],
          meta: { chartId: e.id, width: e.larghezza, height: e.altezza, sliceName: e.g.titolo },
        };
        pos[idRiga].children.push(idGraf);
      });
    }
    var kpi = grafici.filter(function (e) { return e.g.tipo === 'big_number'; });
    var altri = grafici.filter(function (e) { return e.g.tipo !== 'big_number' && e.g.tipo !== 'table'; });
    var tabelle = grafici.filter(function (e) { return e.g.tipo === 'table'; });
    if (kpi.length) {
      var w = Math.max(3, Math.floor(12 / kpi.length));
      riga(kpi.map(function (e) { return Object.assign(e, { larghezza: w, altezza: 25 }); }));
    }
    for (var i = 0; i < altri.length; i += 2) {
      riga(altri.slice(i, i + 2).map(function (e) { return Object.assign(e, { larghezza: 6, altezza: 50 }); }));
    }
    tabelle.forEach(function (e) { riga([Object.assign(e, { larghezza: 12, altezza: 50 })]); });
    return pos;
  }

  function passo(testo, errore) {
    var li = document.createElement('li');
    li.textContent = testo;
    if (errore) li.className = 'err';
    $('log').appendChild(li);
    return li;
  }

  async function creaDashboard() {
    var richiesta = $('richiesta').value.trim();
    if (!richiesta) { messaggio($('msgDash'), 'Descrivi la dashboard.', 'err'); return; }
    $('btnDash').disabled = true;
    $('log').textContent = '';
    nascondi($('msgDash'));
    var fine = cronometro($('tempoDash'));
    try {
      passo('Il modello progetta la dashboard e verifica le query...');
      var piano = await api('POST', '/ai/api/dashboard', { richiesta: richiesta });
      if (!piano.database_id) throw new Error('Database dei dati non registrato in Superset.');
      passo('Piano: "' + piano.titolo + '" con ' + piano.grafici.length + ' grafici.');
      (piano.scartati || []).forEach(function (g) {
        passo('Scartato "' + g.titolo + '" (dopo 2 correzioni): ' + g.errore + (g.sql ? '\nUltima SQL: ' + g.sql : ''), true);
      });

      var dash = (await cerca('/api/v1/dashboard/', [['dashboard_title', 'title_or_slug', piano.titolo]], ['id', 'dashboard_title']))
        .filter(function (d) { return d.dashboard_title === piano.titolo; })[0];
      if (dash) {
        passo('Esiste gia\' una dashboard "' + piano.titolo + '" (id ' + dash.id + '): la aggiorno invece di crearne un\'altra.');
      } else {
        dash = await api('POST', '/api/v1/dashboard/', { dashboard_title: piano.titolo, published: true });
        passo('Dashboard creata (id ' + dash.id + ').');
      }

      var creati = [];
      for (var i = 0; i < piano.grafici.length; i++) {
        var g = piano.grafici[i];
        var li = passo('Grafico "' + g.titolo + '" (' + g.tipo + ')...');
        // Dataset: stesso SQL = stesso nome ("ai_<hash>_...") = riutilizzato
        var prefisso = 'ai_' + hash(g.sql.trim()) + '_';
        var ds = (await cerca('/api/v1/dataset/', [['table_name', 'ct', prefisso]], ['id', 'table_name']))[0];
        var riusoDs = !!ds;
        if (!ds) {
          ds = await api('POST', '/api/v1/dataset/', {
            database: piano.database_id, schema: piano.schema, sql: g.sql,
            table_name: (prefisso + slug(g.titolo)).slice(0, 250),
          });
        }
        var fd = formData(g, ds.id);
        // Grafico: stesso dataset + stesso titolo = aggiornato invece di duplicato
        var ch = (await cerca('/api/v1/chart/', [['datasource_id', 'eq', ds.id], ['datasource_type', 'eq', 'table']], ['id', 'slice_name']))
          .filter(function (c) { return c.slice_name === g.titolo; })[0];
        var riusoCh = !!ch;
        if (ch) {
          await api('PUT', '/api/v1/chart/' + ch.id, { viz_type: fd.viz_type, params: JSON.stringify(fd) });
        } else {
          ch = await api('POST', '/api/v1/chart/', {
            slice_name: g.titolo, viz_type: fd.viz_type, datasource_id: ds.id,
            datasource_type: 'table', params: JSON.stringify(fd), dashboards: [dash.id],
          });
        }
        li.textContent += riusoCh ? ' aggiornato (riutilizzato).' : (riusoDs ? ' creato (dataset riutilizzato).' : ' creato.');
        if (g.nota) passo('Attenzione, "' + g.titolo + '": ' + g.nota + '\nSQL: ' + g.sql, true);
        creati.push({ id: ch.id, g: g });
      }

      await api('PUT', '/api/v1/dashboard/' + dash.id, { position_json: JSON.stringify(layout(piano.titolo, creati)) });
      passo('Layout salvato.');
      var url = '/superset/dashboard/' + dash.id + '/';
      messaggio($('msgDash'), 'Dashboard pronta. Si apre in una nuova scheda: ' + url, 'ok');
      window.open(url, '_blank');
    } catch (e) {
      passo('Errore: ' + e.message, true);
      messaggio($('msgDash'), e.message, 'err');
    } finally {
      fine();
      $('btnDash').disabled = false;
    }
  }

  // ------------------------------------------------------------------ pulizia
  // Elimina i grafici creati dall'AI che non sono in nessuna dashboard e i dataset "ai_*" rimasti senza grafici.
  async function pulisci() {
    if (!confirm('Eliminare i grafici e i dataset creati dall\'AI che NON sono usati in nessuna dashboard?\n(Elimina prima dalle dashboard vecchie quelle che non ti servono.)')) return;
    $('btnPulisci').disabled = true;
    $('log').textContent = '';
    nascondi($('msgDash'));
    try {
      var dataset = await cerca('/api/v1/dataset/', [['table_name', 'ct', 'ai_']], ['id', 'table_name']);
      dataset = dataset.filter(function (d) { return /^ai_/.test(d.table_name); });
      var ids = {}; dataset.forEach(function (d) { ids[d.id] = true; });
      var grafici = await cerca('/api/v1/chart/', [['datasource_type', 'eq', 'table']], ['id', 'slice_name', 'datasource_id', 'dashboards.id']);
      var nCh = 0, usati = {};
      for (var i = 0; i < grafici.length; i++) {
        var c = grafici[i];
        if (!ids[c.datasource_id]) continue;
        if ((c.dashboards || []).length === 0) {
          await api('DELETE', '/api/v1/chart/' + c.id);
          nCh += 1;
        } else {
          usati[c.datasource_id] = true;
        }
      }
      var nDs = 0;
      for (var j = 0; j < dataset.length; j++) {
        if (usati[dataset[j].id]) continue;
        try { await api('DELETE', '/api/v1/dataset/' + dataset[j].id); nDs += 1; } catch (e) { passo('Dataset ' + dataset[j].table_name + ' non eliminato: ' + e.message, true); }
      }
      messaggio($('msgDash'), 'Pulizia completata: eliminati ' + nCh + ' grafici e ' + nDs + ' dataset non usati.', 'ok');
    } catch (e) {
      messaggio($('msgDash'), 'Errore durante la pulizia: ' + e.message, 'err');
    } finally {
      $('btnPulisci').disabled = false;
    }
  }

  // ------------------------------------------------------------------ stato
  async function verificaStato() {
    $('btnStato').disabled = true;
    try {
      var s = await api('GET', '/ai/api/stato');
      alert((s.ok ? 'OK\n' : 'PROBLEMA\n') + s.messaggio + '\n' + (s.database || ''));
    } catch (e) {
      alert('Errore: ' + e.message);
    } finally {
      $('btnStato').disabled = false;
    }
  }

  // ------------------------------------------------------------------ eventi
  $('btnSql').addEventListener('click', generaSql);
  $('btnEsegui').addEventListener('click', rieseguiSql);
  $('btnSqlLab').addEventListener('click', apriSqlLab);
  $('btnCopia').addEventListener('click', function () { navigator.clipboard.writeText($('sql').value); });
  var ordineTemi = ['auto', 'scuro', 'chiaro'];
  function mostraTema() { $('btnTema').textContent = 'Tema: ' + window.aiTemaScelta(); }
  $('btnTema').addEventListener('click', function () {
    var prossimo = ordineTemi[(ordineTemi.indexOf(window.aiTemaScelta()) + 1) % 3];
    try { localStorage.setItem('ai-tema', prossimo); } catch (e) { /* storage non disponibile */ }
    window.aiTema(prossimo);
    mostraTema();
  });
  mostraTema();
  $('btnDash').addEventListener('click', creaDashboard);
  $('btnPulisci').addEventListener('click', pulisci);
  $('btnStato').addEventListener('click', verificaStato);
  $('domanda').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) generaSql(); });
  $('richiesta').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) creaDashboard(); });
  document.querySelectorAll('#esempiSql button').forEach(function (b) {
    b.addEventListener('click', function () { $('domanda').value = b.textContent; generaSql(); });
  });
  document.querySelectorAll('#esempiDash button').forEach(function (b) {
    b.addEventListener('click', function () { $('richiesta').value = b.textContent; });
  });
  caricaInfo().catch(function () { /* mostrato quando serve */ });
})();
