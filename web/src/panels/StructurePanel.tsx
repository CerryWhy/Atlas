import { useState } from "react";
import type { Citation, Structure } from "../api/client";
import { displayName, sceneName, spellId } from "../lib/labels";
import { useAtlasStore } from "../store/atlas";
import type { FmaId } from "../types/ids";
import { CitationList } from "./CitationList";
import { SearchBox } from "./SearchBox";

const LINK =
  "text-iodine-700 underline decoration-iodine-600/40 underline-offset-2 hover:decoration-iodine-700";

type TabKey = "diseases" | "phenotypes" | "parts";

function SourceLink({ cite, children }: { cite: Citation | undefined; children: React.ReactNode }) {
  if (!cite) return <>{children}</>;
  return (
    <a
      href={cite.url}
      target="_blank"
      rel="noreferrer"
      title={`Apri la fonte: ${cite.title}`}
      className={LINK}
    >
      {children}
    </a>
  );
}

function Intro() {
  const regions = useAtlasStore((s) => s.regions);
  const count = useAtlasStore((s) => s.nodes.size);
  const name = sceneName(regions);
  return (
    <div className="pt-6">
      <h2 className="font-serif text-[clamp(1.6rem,4.2vw,2.2rem)] font-medium leading-[1.1] tracking-[-0.01em]">
        {name}
      </h2>
      <p className="mt-3 max-w-[34ch] text-ink-soft">
        {count > 0
          ? `${count} strutture in scena. Clicca un organo per aprirne la scheda, oppure cercalo per nome.`
          : "Sto preparando la tavola."}
      </p>
      <dl className="mt-6 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[0.88rem] text-ink-mute">
        <dt className="text-ink-soft">Trascina</dt>
        <dd>ruota la tavola</dd>
        <dt className="text-ink-soft">Rotella</dt>
        <dd>avvicina e allontana</dd>
        <dt className="text-ink-soft">Tasto destro</dt>
        <dd>sposta l'inquadratura</dd>
        <dt className="text-ink-soft">Legenda</dt>
        <dd>mostra, vela o nasconde un gruppo</dd>
      </dl>
    </div>
  );
}

function Breadcrumbs({ data }: { data: Structure }) {
  const select = useAtlasStore((s) => s.select);
  if (data.ancestors.length === 0) return null;
  return (
    <nav aria-label="Parte di" className="text-[0.8rem] leading-relaxed text-ink-mute">
      <ol className="flex flex-wrap items-baseline gap-x-1">
        {data.ancestors.map((a) => (
          <li key={a.fma_id} className="flex items-baseline gap-x-1">
            <button
              type="button"
              onClick={() => select(a.fma_id)}
              className="cursor-pointer hover:text-iodine-700 hover:underline"
            >
              {displayName(a)}
            </button>
            <span aria-hidden="true" className="text-gauze-300">
              ›
            </span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function Heading({ title, data }: { title: string; data?: Structure }) {
  const cite = (source: string) => data?.citations.find((c) => c.source === source);
  return (
    <header>
      <h2
        data-leader-anchor
        className="font-serif text-[clamp(1.6rem,4.2vw,2.2rem)] font-medium leading-[1.1] tracking-[-0.01em]"
      >
        {title}
      </h2>
      {data && (data.label_la || data.label_it) && (
        <p className="mt-1.5 text-[0.95rem] text-ink-soft">
          {data.label_la && (
            <span className="mr-4">
              <span className="text-ink-mute">lat. </span>
              <i className="font-serif text-[1.05rem]">{data.label_la}</i>
            </span>
          )}
          {data.label_it && (
            <span>
              <span className="text-ink-mute">ingl. </span>
              {data.label_en}
            </span>
          )}
        </p>
      )}
      {data && (
        <p className="tnum mt-2 flex flex-wrap gap-x-4 text-[0.8rem] text-ink-mute">
          <SourceLink cite={cite("fma")}>{spellId(data.fma_id)}</SourceLink>
          {data.uberon_id && (
            <SourceLink cite={cite("uberon")}>{spellId(data.uberon_id)}</SourceLink>
          )}
        </p>
      )}
    </header>
  );
}

/** Comandi di vista sulla selezione: isolarla, o tornare al quadro intero. */
function ViewActions() {
  const isolated = useAtlasStore((s) => s.isolated);
  const toggle = useAtlasStore((s) => s.toggleIsolated);
  const select = useAtlasStore((s) => s.select);
  return (
    <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[0.85rem]">
      <button
        type="button"
        onClick={toggle}
        aria-pressed={isolated}
        className={`cursor-pointer ${LINK}`}
      >
        {isolated ? "Mostra anche il resto" : "Mostra solo questo"}
      </button>
      <button type="button" onClick={() => select(null)} className={`cursor-pointer ${LINK}`}>
        Chiudi la scheda
      </button>
    </div>
  );
}

const isMixed = (items: { inherited: boolean }[]): boolean =>
  items.some((i) => i.inherited) && items.some((i) => !i.inherited);

function UnsidedTag() {
  return (
    <span className="ml-1.5 whitespace-nowrap text-[0.75rem] text-ink-mute">senza lato</span>
  );
}

/**
 * Patologie e segni presi dalla versione senza lato (es. "Right humerus" → "Humerus").
 * Le fonti cliniche raramente distinguono destra e sinistra: lo diciamo, con la fonte
 * che dichiara la relazione, invece di presentarli come specifici di questo lato.
 */
function InheritanceNote({ data }: { data: Structure }) {
  const inheritedItems = [...data.diseases, ...data.phenotypes].filter((i) => i.inherited);
  // solo i legami che portano davvero voci: gli altri non spiegano nulla di ciò che si vede
  const links = data.inherited_from.filter((l) => l.carries_content);
  if (inheritedItems.length === 0 || links.length === 0) return null;
  const all = inheritedItems.length === data.diseases.length + data.phenotypes.length;
  return (
    <p className="mt-4 border-l-2 border-iodine-600 pl-3 text-[0.88rem] text-ink-soft">
      Le fonti cliniche descrivono{" "}
      {links.map((l, i) => (
        <span key={l.uberon_id}>
          {i > 0 && (i === links.length - 1 ? " e " : ", ")}
          <SourceLink cite={l.citations[0]}>
            <span className="font-serif italic">{l.unsided_label}</span>
          </SourceLink>
        </span>
      ))}{" "}
      senza distinguere il lato.{" "}
      {all
        ? "Le voci qui sotto valgono per la struttura in generale, non specificamente per questo lato."
        : "Le voci segnate «senza lato» valgono per la struttura in generale, non specificamente per questo lato."}
    </p>
  );
}

function Entry({ data }: { data: Structure }) {
  const select = useAtlasStore((s) => s.select);
  const tabs: { key: TabKey; label: string; n: number }[] = [
    { key: "diseases", label: "Patologie", n: data.diseases.length },
    { key: "phenotypes", label: "Segni", n: data.phenotypes.length },
    { key: "parts", label: "Parti", n: data.children.length },
  ];
  const firstFilled = tabs.find((t) => t.n > 0)?.key ?? "diseases";
  const [picked, setPicked] = useState<TabKey | null>(null);
  const tab = picked && tabs.some((t) => t.key === picked && t.n > 0) ? picked : firstFilled;
  const nothing = tabs.every((t) => t.n === 0);
  // Il segno "senza lato" serve solo se una lista mescola voci proprie ed ereditate;
  // quando sono tutte ereditate lo dice già la nota in alto.
  const mixed = {
    diseases: isMixed(data.diseases),
    phenotypes: isMixed(data.phenotypes),
  };

  const citations = [
    ...data.citations,
    ...data.inherited_from.flatMap((l) => l.citations),
    ...data.diseases.flatMap((d) => d.citations),
    ...data.phenotypes.flatMap((p) => p.citations),
  ];

  return (
    <div className="pt-5">
      <Breadcrumbs data={data} />
      <div className="mt-1.5">
        <Heading title={displayName(data)} data={data} />
      </div>
      <ViewActions />

      <InheritanceNote data={data} />

      {data.diseases.length + data.phenotypes.length === 0 && (
        <p className="mt-4 border-l-2 border-gauze-300 pl-3 text-[0.88rem] text-ink-soft">
          {data.uberon_id || data.inherited_from.length > 0
            ? "Le fonti caricate non collegano patologie o segni a questa struttura, né alla sua versione senza lato: di solito li registrano su una struttura più ampia."
            : "Questa struttura non ha un collegamento alle ontologie cliniche."}{" "}
          {data.ancestors.length > 0 && "Risali la gerarchia qui sopra per trovarli."}
        </p>
      )}

      {!nothing && (
        <div role="tablist" aria-label="Contenuti della scheda" className="mt-6 flex gap-5">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              disabled={t.n === 0}
              onClick={() => setPicked(t.key)}
              className={`-mb-px cursor-pointer border-b-2 pb-1.5 text-[0.92rem] disabled:cursor-default disabled:text-gauze-300 ${
                tab === t.key
                  ? "border-iodine-600 font-semibold text-ink"
                  : "border-transparent text-ink-mute hover:text-ink"
              }`}
            >
              {t.label} <span className="tnum font-normal text-ink-mute">{t.n}</span>
            </button>
          ))}
        </div>
      )}

      <div role="tabpanel" className="border-t border-gauze-300">
        {tab === "diseases" && data.diseases.length > 0 && (
          <ul>
            {data.diseases.map((d) => {
              const mondo = d.citations.find((c) => c.source === "mondo");
              const icd = d.citations.find((c) => c.source === "icd11");
              return (
                <li
                  key={d.mondo_id}
                  className="flex items-baseline justify-between gap-3 border-b border-gauze-200 py-2"
                >
                  <div className="min-w-0">
                    <div className="leading-snug">
                      {d.label}
                      {mixed.diseases && d.inherited && <UnsidedTag />}
                    </div>
                    <div className="tnum text-[0.78rem] text-ink-mute">
                      <SourceLink cite={mondo}>{spellId(d.mondo_id)}</SourceLink>
                    </div>
                  </div>
                  {d.icd11_code && (
                    <a
                      href={icd?.url}
                      target="_blank"
                      rel="noreferrer"
                      title={`Codice ICD-11 MMS ${icd?.version ?? ""}. Apri la fonte.`}
                      className="tnum shrink-0 rounded-[3px] bg-iodine-100 px-1.5 py-0.5 text-[0.8rem] font-medium text-iodine-700 hover:bg-iodine-300"
                    >
                      {d.icd11_code}
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {tab === "phenotypes" && data.phenotypes.length > 0 && (
          <ul>
            {data.phenotypes.map((p) => (
              <li
                key={p.hpo_id}
                className="flex items-baseline justify-between gap-3 border-b border-gauze-200 py-1.5"
              >
                <span className="leading-snug">
                  {p.label}
                  {mixed.phenotypes && p.inherited && <UnsidedTag />}
                </span>
                <span className="tnum shrink-0 text-[0.78rem] text-ink-mute">
                  <SourceLink cite={p.citations[0]}>{spellId(p.hpo_id)}</SourceLink>
                </span>
              </li>
            ))}
          </ul>
        )}

        {tab === "parts" && data.children.length > 0 && (
          <>
            <ul>
              {data.children.map((c) => (
                <li key={c.fma_id} className="border-b border-gauze-200">
                  <button
                    type="button"
                    onClick={() => select(c.fma_id as FmaId)}
                    className="flex w-full cursor-pointer items-baseline gap-2 py-1.5 text-left hover:text-iodine-700"
                  >
                    <span
                      aria-hidden="true"
                      className={`mb-px inline-block size-1.5 shrink-0 self-center rounded-full ${
                        c.has_uberon ? "bg-iodine-600" : "bg-gauze-300"
                      }`}
                    />
                    <span className="leading-snug">{displayName(c)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {data.children.some((c) => c.has_uberon) && (
              <p className="mt-2 flex items-center gap-2 text-[0.78rem] text-ink-mute">
                <span
                  aria-hidden="true"
                  className="inline-block size-1.5 rounded-full bg-iodine-600"
                />
                ha un collegamento clinico
              </p>
            )}
          </>
        )}
      </div>

      <CitationList citations={citations} />
    </div>
  );
}

/** La scheda: cosa hai selezionato, cosa lo riguarda, da dove viene ogni voce. */
export function StructurePanel() {
  const detail = useAtlasStore((s) => s.detail);
  const selected = useAtlasStore((s) => s.selected);
  const select = useAtlasStore((s) => s.select);
  // Il nome noto prima che arrivi la scheda: dal nodo o dal suo organo di fuoco.
  const known = useAtlasStore((s) => {
    if (!s.selected) return null;
    const own = s.nodes.get(s.selected);
    if (own) return displayName(own);
    for (const n of s.nodes.values()) {
      if (n.focus_fma_id === s.selected) {
        return displayName({ label_en: n.focus_label_en, label_it: n.focus_label_it });
      }
    }
    return null;
  });

  return (
    <aside
      data-sheet
      aria-label="Scheda della struttura"
      className="sheet absolute inset-x-0 bottom-0 h-[var(--sheet-h)] overflow-y-auto rounded-t-md wide:inset-x-auto wide:bottom-4 wide:right-4 wide:top-4 wide:h-auto wide:w-[var(--sheet-w)] wide:rounded-md"
    >
      <div className="sticky top-0 z-10 bg-gauze-100 px-6 pt-3">
        <SearchBox />
      </div>
      <div className="px-6 pb-7">
        {detail.state === "idle" && <Intro />}
        {detail.state === "loading" && (
          <div className="pt-5">
            <Heading title={known ?? "…"} />
            <p className="mt-3 text-[0.9rem] text-ink-mute">Carico la scheda.</p>
          </div>
        )}
        {detail.state === "error" && (
          <div className="pt-5">
            <Heading title={known ?? "Scheda non disponibile"} />
            <p className="mt-3 text-[0.9rem] text-ink-soft">
              Non riesco a leggere la scheda dal server. {detail.message}.
            </p>
            {selected && (
              <button
                type="button"
                onClick={() => select(selected)}
                className={`mt-2 cursor-pointer text-[0.9rem] ${LINK}`}
              >
                Riprova
              </button>
            )}
          </div>
        )}
        {detail.state === "ok" && <Entry key={detail.data.fma_id} data={detail.data} />}
      </div>
    </aside>
  );
}
