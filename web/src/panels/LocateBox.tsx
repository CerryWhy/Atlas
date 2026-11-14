import { useState } from "react";
import { displayName } from "../lib/labels";
import { useAtlasStore } from "../store/atlas";

const LINK =
  "text-iodine-700 underline decoration-iodine-600/40 underline-offset-2 hover:decoration-iodine-700";

/**
 * Dal sintomo al corpo (Fase 5): un segno descritto in parole proprie → i fenotipi HPO
 * più vicini → le strutture dove hanno sede, accese nella scena. Descrive dove un segno
 * ha sede in generale; non valuta la situazione di una persona (SPEC §9). Il testo non
 * viene salvato.
 */
export function LocateBox() {
  const [text, setText] = useState("");
  const located = useAtlasStore((s) => s.located);
  const locate = useAtlasStore((s) => s.locate);
  const clear = useAtlasStore((s) => s.clearLocated);
  const select = useAtlasStore((s) => s.select);
  const ready = text.trim().length >= 2;

  return (
    <section aria-labelledby="locate-title" className="mt-8 border-t border-gauze-200 pt-5">
      <h3 id="locate-title" className="font-serif text-[1.15rem] font-medium">
        Dal sintomo al corpo
      </h3>
      <p className="mt-1 text-[0.85rem] text-ink-mute">
        Descrivi un segno in generale, per esempio «sangue dal naso» o «mal di schiena».
      </p>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) locate(text.trim());
        }}
      >
        <input
          type="text"
          value={text}
          maxLength={300}
          onChange={(e) => setText(e.target.value)}
          aria-label="Segno o sintomo"
          placeholder="un segno o un sintomo…"
          className="min-w-0 flex-1 border-b border-gauze-300 bg-transparent py-1 text-[0.95rem] outline-none placeholder:text-ink-mute focus:border-iodine-600"
        />
        <button
          type="submit"
          disabled={!ready || located.state === "loading"}
          className={`cursor-pointer text-[0.9rem] disabled:cursor-default disabled:text-gauze-300 ${LINK}`}
        >
          Localizza
        </button>
      </form>

      {located.state === "loading" && (
        <p className="mt-3 text-[0.85rem] text-ink-mute">Cerco i segni più vicini…</p>
      )}
      {located.state === "error" && (
        <p className="mt-3 text-[0.85rem] text-ink-soft">
          Non riesco a localizzare: {located.message}.
        </p>
      )}
      {located.state === "ok" && (
        <div className="mt-4">
          {located.data.structures.length === 0 ? (
            <p className="text-[0.85rem] text-ink-soft">
              Nessun segno vicino porta a una struttura in scena.
            </p>
          ) : (
            <>
              <p className="text-[0.8rem] uppercase tracking-wide text-ink-mute">Dove ha sede</p>
              <ul className="mt-1">
                {located.data.structures.map((s) => (
                  <li key={s.fma_id} className="border-b border-gauze-200">
                    <button
                      type="button"
                      onClick={() => select(s.fma_id)}
                      className="w-full cursor-pointer py-1.5 text-left hover:text-iodine-700"
                    >
                      {displayName(s)}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-[0.8rem] uppercase tracking-wide text-ink-mute">
                Segni HPO più vicini
              </p>
              <ul className="mt-1 text-[0.88rem]">
                {located.data.phenotypes.map((p) => (
                  <li key={p.hpo_id} className="py-0.5">
                    <a href={p.citations[0]?.url} target="_blank" rel="noreferrer" className={LINK}>
                      {p.label}
                    </a>
                    {p.basis === "inherited" && (
                      <span className="text-[0.78rem] text-ink-mute">
                        {" "}
                        — sede da{" "}
                        <a
                          href={p.citations[1]?.url}
                          target="_blank"
                          rel="noreferrer"
                          className={LINK}
                        >
                          {p.via_label}
                        </a>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
          <button type="button" onClick={clear} className={`mt-3 text-[0.85rem] ${LINK}`}>
            Cancella
          </button>
        </div>
      )}
      <p className="mt-4 text-[0.78rem] text-ink-mute">
        Indica dove un segno ha sede in generale, secondo HPO. Non valuta la situazione di una
        persona: per un disturbo reale rivolgersi a un medico.
      </p>
    </section>
  );
}
