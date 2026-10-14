import { useEffect, useMemo, useState } from 'react';
import type { Article, Dataset } from './types';

const APP_VERSION = '0.1.0';
const STALE_HOURS = 48;
const IMPORTANCE_LABEL: Record<number, string> = { 3: '高', 2: '中', 1: '低' };
const FAV_KEY = 'aitopics.favorites';
const PAGE_KEY = 'aitopics.pageSize';

type View = 'home' | 'list' | 'detail' | 'settings' | 'logs';

interface Filters {
  q: string;
  category: string;
  source: string;
  minImportance: number;
  from: string;
  to: string;
  favOnly: boolean;
  sort: 'new' | 'importance';
}

const EMPTY_FILTERS: Filters = { q: '', category: '', source: '', minImportance: 1, from: '', to: '', favOnly: false, sort: 'new' };

const fmt = (iso: string | null, withTime = true) =>
  iso
    ? new Date(iso).toLocaleString('ja-JP', {
        timeZone: 'Asia/Tokyo',
        year: 'numeric', month: '2-digit', day: '2-digit',
        ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
      })
    : '不明';

const jstDay = (iso: string) => new Date(iso).toLocaleDateString('sv-SE', { timeZone: 'Asia/Tokyo' });
const articleDate = (a: Article) => a.publishedAt ?? a.fetchedAt;

function loadFavorites(): Set<number> {
  try {
    return new Set(JSON.parse(localStorage.getItem(FAV_KEY) ?? '[]') as number[]);
  } catch {
    return new Set();
  }
}

function loadPageSize(): number {
  try {
    return Number(localStorage.getItem(PAGE_KEY)) || 30;
  } catch {
    return 30;
  }
}

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>('home');
  const [selected, setSelected] = useState<Article | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [favs, setFavs] = useState<Set<number>>(loadFavorites);
  const [showQr, setShowQr] = useState(false);
  const [cameFrom, setCameFrom] = useState<View>('list');
  const [pageSize, setPageSize] = useState<number>(loadPageSize);
  const [shown, setShown] = useState<number>(pageSize);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/articles.json`, { cache: 'no-cache' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Dataset>;
      })
      .then(setData)
      .catch((e) => setError(`データを読み込めませんでした: ${e.message}`));
  }, []);

  const toggleFav = (id: number) => {
    setFavs((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      try {
        localStorage.setItem(FAV_KEY, JSON.stringify([...next]));
      } catch { /* 保存できなくても動作は継続 */ }
      return next;
    });
  };

  const filtered = useMemo(() => {
    if (!data) return [];
    const kw = filters.q.trim().toLowerCase();
    const list = data.articles.filter((a) => {
      if (filters.category && !a.categories.includes(filters.category)) return false;
      if (filters.source && a.sourceId !== filters.source) return false;
      if (a.importance < filters.minImportance) return false;
      if (filters.favOnly && !favs.has(a.id)) return false;
      const day = jstDay(articleDate(a));
      if (filters.from && day < filters.from) return false;
      if (filters.to && day > filters.to) return false;
      if (kw) {
        const hay = `${a.titleJa ?? ''} ${a.title} ${a.summary ?? ''} ${a.source} ${a.keywords.join(' ')}`.toLowerCase();
        if (!kw.split(/\s+/).every((w) => hay.includes(w))) return false;
      }
      return true;
    });
    list.sort((a, b) =>
      filters.sort === 'importance' && b.importance !== a.importance
        ? b.importance - a.importance
        : articleDate(b).localeCompare(articleDate(a)));
    return list;
  }, [data, filters, favs]);

  const openList = (patch: Partial<Filters> = {}) => {
    setFilters({ ...EMPTY_FILTERS, ...patch });
    setShown(pageSize);
    setView('list');
  };
  const openDetail = (a: Article) => {
    if (view !== 'detail') setCameFrom(view);
    setSelected(a);
    setView('detail');
    window.scrollTo(0, 0);
  };
  const back = () => setView(view === 'detail' ? cameFrom : 'home');

  if (error) return <Shell><p className="banner error">{error}</p></Shell>;
  if (!data) return <Shell><p className="muted">読み込み中…</p></Shell>;

  const title: Record<View, string> = {
    home: 'トピックス', list: '記事一覧', detail: '記事詳細', settings: '設定', logs: '取得履歴',
  };

  return (
    <Shell wide={view === 'home' || view === 'list'}>
      <header className="topbar">
        <div className="topbar-left">
          {view === 'home' ? (
            <button className="home-btn" aria-label="記事一覧を開く" onClick={() => openList()}>記事一覧</button>
          ) : (
            <button className="home-btn" aria-label="トピックスのページに戻る" onClick={() => setView('home')}>← トピックス</button>
          )}
          <h1>{title[view]}</h1>
        </div>
        <div className="topbar-actions">
          <input
              className="top-search"
              type="search"
              placeholder="キーワード検索"
              aria-label="キーワード検索"
              value={filters.q}
              onChange={(e) => { setFilters({ ...filters, q: e.target.value }); setShown(pageSize); }}
              onKeyDown={(e) => { if (e.key === 'Enter' && view !== 'list') setView('list'); }}
            />
          <button className="icon-btn qr-btn" aria-label="スマホ用QRコード" onClick={() => setShowQr(true)}>QR</button>
          <button className="icon-btn" aria-label="設定" onClick={() => setView('settings')}>⚙️</button>
          {view !== 'home' && view !== 'list' && (
            <button className="icon-btn" aria-label="戻る" onClick={back}>✕</button>
          )}
        </div>
      </header>

      {view === 'home' && <Home data={data} openList={openList} openDetail={openDetail} favs={favs} toggleFav={toggleFav} openLogs={() => setView('logs')} />}

      {view === 'list' && (
        <>
          <FilterPanel data={data} filters={filters} setFilters={(f) => { setFilters(f); setShown(pageSize); }} />
          <p className="muted">{filtered.length} 件</p>
          <div className="card-grid">
            {filtered.slice(0, shown).map((a) => (
              <Card key={a.id} a={a} fav={favs.has(a.id)} toggleFav={toggleFav} onOpen={() => openDetail(a)} />
            ))}
          </div>
          {filtered.length === 0 && <p className="muted">条件に一致する記事はありません。</p>}
          {shown < filtered.length && (
            <button className="btn" onClick={() => setShown(shown + pageSize)}>さらに表示</button>
          )}
        </>
      )}

      {view === 'detail' && selected && (
        <Detail a={selected} fav={favs.has(selected.id)} toggleFav={toggleFav}
          related={data.articles.filter((x) => x.id !== selected.id && x.categories.some((c) => selected.categories.includes(c)) && x.keywords.some((k) => selected.keywords.includes(k))).slice(0, 5)}
          openDetail={openDetail} />
      )}

      {view === 'settings' && (
        <Settings data={data} pageSize={pageSize} setPageSize={(n) => {
          setPageSize(n);
          setShown(n);
          try { localStorage.setItem(PAGE_KEY, String(n)); } catch { /* 無視 */ }
        }} openLogs={() => setView('logs')} />
      )}

      {view === 'logs' && <Logs data={data} />}

      {showQr && (
        <div className="modal" role="dialog" aria-modal="true" onClick={() => setShowQr(false)}>
          <div className="modal-body" onClick={(e) => e.stopPropagation()}>
            <button className="icon-btn modal-close" aria-label="閉じる" onClick={() => setShowQr(false)}>✕</button>
            <h2>スマホで開く</h2>
            <img src={`${import.meta.env.BASE_URL}qr.svg`} alt="スマホ版を開くQRコード" width={260} height={260} />
            <p className="muted tiny">スマホのカメラで読み取ってください。<br />https://moppe1979.github.io/AITopics/</p>
          </div>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  return <div className={wide ? 'app wide' : 'app'}>{children}</div>;
}

function StatusBanner({ data }: { data: Dataset }) {
  const failed = data.sources.filter((s) => s.status === 'error').length;
  const ageH = data.lastRunAt ? (Date.now() - new Date(data.lastRunAt).getTime()) / 3600000 : Infinity;
  return (
    <>
      {ageH > STALE_HOURS && (
        <p className="banner warn">最終取得から {Number.isFinite(ageH) ? `${Math.floor(ageH)} 時間` : '長時間'}以上経過しています。情報が古い可能性があります。</p>
      )}
      {failed > 0 && <p className="banner error">取得に失敗した情報源が {failed} 件あります。取得履歴で確認してください。</p>}
    </>
  );
}

function Home({ data, openList, openDetail, favs, toggleFav, openLogs }: {
  data: Dataset; openList: (p?: Partial<Filters>) => void; openDetail: (a: Article) => void;
  favs: Set<number>; toggleFav: (id: number) => void; openLogs: () => void;
}) {
  const important = data.articles.filter((a) => a.importance === 3).slice(0, 50);
  const latest = data.articles.slice(0, 50);
  const section = (heading: string, items: Article[], more?: () => void, scroll = false) => (
    <section className={scroll ? 'section col' : 'section'}>
      <div className="section-head"><h2>{heading}</h2>{more && <button className="link" onClick={more}>もっと見る</button>}</div>
      <div className={scroll ? 'col-scroll' : undefined}>
        {items.length === 0 && <p className="muted">該当する記事はまだありません。</p>}
        {items.map((a) => <Card key={a.id} a={a} compact fav={favs.has(a.id)} toggleFav={toggleFav} onOpen={() => openDetail(a)} />)}
      </div>
    </section>
  );
  return (
    <>
      <StatusBanner data={data} />
      <div className="homebar">
        <span className="muted">最終取得: {fmt(data.lastRunAt)}（日本時間）</span>
        <button className="link" onClick={openLogs}>取得履歴</button>
      </div>

      <div className="cols">
        {section('重要なトピックス', important, () => openList({ minImportance: 3 }), true)}
        {section('最新トピックス', latest, () => openList(), true)}
      </div>
    </>
  );
}

function Stars({ n }: { n: number }) {
  return <span className={`imp imp-${n}`}>重要度 {IMPORTANCE_LABEL[n]}</span>;
}

function Card({ a, fav, toggleFav, onOpen }: {
  a: Article; fav: boolean; toggleFav: (id: number) => void; onOpen: () => void; compact?: boolean;
}) {
  return (
    <article className="card">
      <div className="card-meta">
        <span>{fmt(a.publishedAt, false)}</span><span>{a.source}</span><Stars n={a.importance} />
      </div>
      <h3><button className="card-title" onClick={onOpen}>{a.titleJa ?? a.title}</button></h3>
      {a.titleJa && <p className="muted tiny orig">原題: {a.title}</p>}
      {a.summary ? <p className="summary clamp3">{a.summary}</p> : <p className="muted tiny">概要を取得できませんでした。</p>}
      <div className="card-actions">
        <div className="card-left">
          <button className={`fav ${fav ? 'on' : ''}`} onClick={() => toggleFav(a.id)} aria-pressed={fav}>
            {fav ? '★ お気に入り' : '☆ お気に入り'}
          </button>
          {a.categories.map((c) => <span key={c} className="tag">{c}</span>)}
        </div>
        <a href={a.url} target="_blank" rel="noopener noreferrer">元記事を開く ↗</a>
      </div>
    </article>
  );
}

function Summary({ a }: { a: Article }) {
  if (a.summaryKind === 'none' || !a.summary)
    return <p className="muted">概要を取得できませんでした（元記事をご確認ください）。</p>;
  return (
    <>
      <p className="summary">{a.summary}</p>
      {a.summaryKind === 'excerpt' && <p className="muted tiny">※配信元の概要の抜粋です（AI要約は使用していません）。</p>}
      {a.usagePoints && <p className="usage"><b>業務活用の着眼点（カテゴリからの目安）:</b><br />{a.usagePoints}</p>}
    </>
  );
}

function Detail({ a, fav, toggleFav, related, openDetail }: {
  a: Article; fav: boolean; toggleFav: (id: number) => void; related: Article[]; openDetail: (a: Article) => void;
}) {
  return (
    <article className="detail">
      <h2>{a.titleJa ?? a.title}</h2>
      {a.titleJa && <p className="muted tiny orig">原題: {a.title}（日本語タイトルは機械翻訳です）</p>}
      <p className="muted">公開日: {fmt(a.publishedAt)} ／ 取得日: {fmt(a.fetchedAt)} ／ 発信元: {a.source}</p>
      <div className="chips small"><Stars n={a.importance} />{a.categories.map((c) => <span key={c} className="tag">{c}</span>)}</div>
      <h3>概要</h3>
      <Summary a={a} />
      <h3>業務活用の可能性</h3>
      <p className="usage">{a.usagePoints ?? '該当するカテゴリがないため、活用の着眼点はありません。'}</p>
      {a.usagePoints && <p className="muted tiny">※記事内容の要約ではなく、カテゴリに基づく自動の目安です。実際の適用可否は元記事でご確認ください。</p>}
      <h3>関連キーワード</h3>
      <div className="chips small">{a.keywords.length ? a.keywords.map((k) => <span key={k} className="tag">{k}</span>) : <span className="muted">なし</span>}</div>
      <div className="card-actions">
        <button className={`fav ${fav ? 'on' : ''}`} onClick={() => toggleFav(a.id)}>{fav ? '★ お気に入り' : '☆ お気に入り'}</button>
        <a className="btn primary" href={a.url} target="_blank" rel="noopener noreferrer">元記事を開く ↗</a>
      </div>
      {related.length > 0 && (
        <>
          <h3>関連記事</h3>
          {related.map((r) => <button key={r.id} className="link block" onClick={() => openDetail(r)}>{r.titleJa ?? r.title}</button>)}
        </>
      )}
    </article>
  );
}

function FilterPanel({ data, filters, setFilters }: { data: Dataset; filters: Filters; setFilters: (f: Filters) => void }) {
  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters({ ...filters, [k]: v });
  return (
    <section className="filters">
      <div className="row">
        <select value={filters.category} onChange={(e) => set('category', e.target.value)} aria-label="カテゴリ">
          <option value="">全カテゴリ</option>
          {data.categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select value={filters.source} onChange={(e) => set('source', e.target.value)} aria-label="情報発信元">
          <option value="">全発信元</option>
          {data.sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div className="row">
        <label>期間 <input type="date" value={filters.from} onChange={(e) => set('from', e.target.value)} /></label>
        <label>〜 <input type="date" value={filters.to} onChange={(e) => set('to', e.target.value)} /></label>
      </div>
      <div className="row">
        <select value={filters.minImportance} onChange={(e) => set('minImportance', Number(e.target.value))} aria-label="重要度">
          <option value={1}>重要度: すべて</option>
          <option value={2}>重要度: 中以上</option>
          <option value={3}>重要度: 高のみ</option>
        </select>
        <select value={filters.sort} onChange={(e) => set('sort', e.target.value as Filters['sort'])} aria-label="並べ替え">
          <option value="new">新着順</option>
          <option value="importance">重要度順</option>
        </select>
      </div>
      <label className="check"><input type="checkbox" checked={filters.favOnly} onChange={(e) => set('favOnly', e.target.checked)} /> お気に入りのみ</label>
    </section>
  );
}

function Settings({ data, pageSize, setPageSize, openLogs }: {
  data: Dataset; pageSize: number; setPageSize: (n: number) => void; openLogs: () => void;
}) {
  return (
    <>
      <section className="section">
        <h2>アプリ情報</h2>
        <dl className="kv">
          <dt>ユーザーID</dt><dd>未設定（ログイン機能なし）</dd>
          <dt>ユーザー名</dt><dd>未設定</dd>
          <dt>アプリバージョン</dt><dd>{APP_VERSION}</dd>
          <dt>データ生成日時</dt><dd>{fmt(data.generatedAt)}</dd>
          <dt>最終取得日時</dt><dd>{fmt(data.lastRunAt)}</dd>
          <dt>端末</dt><dd className="break">{navigator.userAgent}</dd>
        </dl>
      </section>
      <section className="section">
        <h2>この端末で変更できる設定</h2>
        <label className="check">1回の表示件数
          <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
            {[10, 30, 50, 100].map((n) => <option key={n} value={n}>{n} 件</option>)}
          </select>
        </label>
        <p className="muted tiny">お気に入りと表示件数はこの端末のブラウザ内にのみ保存されます。</p>
      </section>
      <section className="section">
        <h2>変更できない設定（制約）</h2>
        <ul className="constraints">
          <li><b>取得頻度:</b> 1日1回（GitHub Actions のスケジュールで固定）。変更はリポジトリの workflow ファイルの編集が必要です。</li>
          <li><b>手動更新:</b> この画面からは実行できません。GitHub の Actions 画面で「Run workflow」を実行するか、PCで <code>python collector/collect.py</code> を実行してください。</li>
          <li><b>情報取得元・収集キーワード・重要度判定基準:</b> <code>collector/sources.json</code> と <code>collector/classify.py</code> で管理します（画面からは変更不可）。</li>
        </ul>
      </section>
      <section className="section">
        <h2>情報取得元（{data.sources.length} 件）</h2>
        <ul className="plain">
          {data.sources.map((s) => (
            <li key={s.id}>{s.name} — {s.enabled ? (s.status === 'ok' ? '取得成功' : `状態: ${s.status ?? '未取得'}`) : '無効'}</li>
          ))}
        </ul>
        <button className="btn" onClick={openLogs}>取得履歴を見る</button>
      </section>
    </>
  );
}

function Logs({ data }: { data: Dataset }) {
  return (
    <>
      <section className="section">
        <h2>情報源の状態</h2>
        {data.sources.map((s) => (
          <div key={s.id} className={`log ${s.status === 'error' ? 'bad' : ''}`}>
            <b>{s.name}</b> <span className="muted">{s.status ?? '未取得'} / {fmt(s.lastFetchedAt)}</span>
            {s.error && <div className="errtext">{s.error}</div>}
          </div>
        ))}
      </section>
      <section className="section">
        <h2>実行履歴（直近100件）</h2>
        {data.logs.map((l, i) => (
          <div key={i} className={`log ${l.error ? 'bad' : ''}`}>
            <span className="muted">{fmt(l.runAt)}</span> <b>{l.source}</b><br />
            取得 {l.processed} / 新規 {l.success} / 失敗 {l.failed}
            {l.error && <div className="errtext">{l.error}</div>}
          </div>
        ))}
      </section>
    </>
  );
}
