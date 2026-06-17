/**
 * Observables list (Phase 2). Read-only. data_type/data/IOC flag/tags.
 */

import { useEffect, useState } from "react";

import { Link } from "@tanstack/react-router";

import { TLPBadge, type TLPValue } from "@/design-system/components/TLPBadge";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/ui/Toast";

interface ObservableRow {
  id: string;
  data_type: string;
  data: string;
  tlp: TLPValue;
  pap: string;
  tags: string[];
  is_ioc: boolean;
  sighted: boolean;
  message: string | null;
  created_at: string;
}

export function ObservablesPage() {
  const { apiCall, permissions } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<ObservableRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [csvText, setCsvText] = useState(
    "data_type,data,tlp,is_ioc,tags,message\nip,1.2.3.4,amber,true,phish,seen in mail bounce\n",
  );
  const [importBusy, setImportBusy] = useState(false);
  const initialView = (() => {
    try {
      const raw = window.localStorage.getItem("adhkar.observables.view");
      if (!raw)
        return {
          type: "",
          tag: "",
          ioc: "" as const,
          sighted: "" as const,
          tlp: "",
          updatedWithin: 0 as 0 | 24 | 168 | 720,
        };
      const p = JSON.parse(raw) as {
        type?: string;
        tag?: string;
        ioc?: "" | "true" | "false";
        sighted?: "" | "true" | "false";
        tlp?: string;
        updatedWithin?: number;
      };
      const uw =
        p.updatedWithin === 24 || p.updatedWithin === 168 || p.updatedWithin === 720
          ? (p.updatedWithin as 24 | 168 | 720)
          : (0 as const);
      return {
        type: p.type ?? "",
        tag: p.tag ?? "",
        ioc: (p.ioc ?? "") as "" | "true" | "false",
        sighted: (p.sighted ?? "") as "" | "true" | "false",
        tlp: p.tlp ?? "",
        updatedWithin: uw as 0 | 24 | 168 | 720,
      };
    } catch {
      return {
        type: "",
        tag: "",
        ioc: "" as const,
        sighted: "" as const,
        tlp: "",
        updatedWithin: 0 as 0 | 24 | 168 | 720,
      };
    }
  })();
  const urlOverride = (() => {
    if (typeof window === "undefined") return {};
    const sp = new URLSearchParams(window.location.search);
    const out: Partial<{
      filterType: string;
      filterTag: string;
      filterIoc: "" | "true" | "false";
      filterSighted: "" | "true" | "false";
      filterTlp: string;
      updatedWithin: 0 | 24 | 168 | 720;
    }> = {};
    const dt = sp.get("data_type");
    if (dt !== null) out.filterType = dt;
    const tag = sp.get("tag");
    if (tag !== null) out.filterTag = tag;
    const ioc = sp.get("is_ioc");
    if (ioc === "true" || ioc === "false") out.filterIoc = ioc;
    const sighted = sp.get("sighted");
    if (sighted === "true" || sighted === "false") out.filterSighted = sighted;
    const tlp = sp.get("tlp");
    if (
      tlp === "white" ||
      tlp === "green" ||
      tlp === "amber" ||
      tlp === "amber-strict" ||
      tlp === "red"
    )
      out.filterTlp = tlp;
    const uwRaw = sp.get("updated_within_hours");
    if (uwRaw !== null) {
      const n = Number.parseInt(uwRaw, 10);
      if (n === 24 || n === 168 || n === 720) out.updatedWithin = n;
      else if (n === 0) out.updatedWithin = 0;
    }
    return out;
  })();
  const [filterType, setFilterType] = useState<string>(urlOverride.filterType ?? initialView.type);
  const [filterTag, setFilterTag] = useState<string>(urlOverride.filterTag ?? initialView.tag);
  const [filterIoc, setFilterIoc] = useState<"" | "true" | "false">(urlOverride.filterIoc ?? initialView.ioc);
  const [filterSighted, setFilterSighted] = useState<"" | "true" | "false">(
    urlOverride.filterSighted ?? initialView.sighted,
  );
  const [filterTlp, setFilterTlp] = useState<string>(urlOverride.filterTlp ?? initialView.tlp);
  const [updatedWithin, setUpdatedWithin] = useState<0 | 24 | 168 | 720>(
    urlOverride.updatedWithin ?? initialView.updatedWithin,
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(
        "adhkar.observables.view",
        JSON.stringify({
          type: filterType,
          tag: filterTag,
          ioc: filterIoc,
          sighted: filterSighted,
          tlp: filterTlp,
          updatedWithin,
        }),
      );
    } catch {
      /* localStorage disabled (private mode, quota) — best-effort */
    }
  }, [filterType, filterTag, filterIoc, filterSighted, filterTlp, updatedWithin]);

  const refresh = async () => {
    try {
      const params = new URLSearchParams({ limit: "500" });
      if (filterType.trim()) params.set("data_type", filterType.trim());
      if (filterTag.trim()) params.set("tag", filterTag.trim());
      if (filterIoc) params.set("is_ioc", filterIoc);
      if (filterSighted) params.set("sighted", filterSighted);
      if (filterTlp) params.set("tlp", filterTlp);
      if (updatedWithin >= 1) {
        const since = new Date(Date.now() - updatedWithin * 3600 * 1000).toISOString();
        params.set("updated_since", since);
      }
      const r = await apiCall<ObservableRow[]>(
        `/v1/observables?${params.toString()}`,
      );
      setRows(r);
      setSelected(new Set());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiCall, filterType, filterTag, filterIoc, filterSighted, filterTlp, updatedWithin]);

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulkMarkIoc = async () => {
    if (selected.size === 0) return;
    setBulkBusy(true);
    try {
      const r = await apiCall<{ updated: number }>("/v1/observables/bulk-patch", {
        method: "POST",
        body: JSON.stringify({
          ids: Array.from(selected),
          patch: { is_ioc: true },
        }),
      });
      toast.success(`Marked ${r.updated} observable(s) as IOC.`);
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBulkBusy(false);
    }
  };

  const canManage = permissions.has("manageObservable");

  const importCsv = async () => {
    if (!csvText.trim()) return;
    setImportBusy(true);
    try {
      const r = await apiCall<{
        imported: number;
        skipped_duplicate: number;
        skipped_invalid: number;
      }>("/v1/observables/import-csv", {
        method: "POST",
        body: JSON.stringify({ csv_text: csvText }),
      });
      toast.success(
        `Imported ${r.imported}, dedup ${r.skipped_duplicate}, invalid ${r.skipped_invalid}.`,
      );
      setShowImport(false);
      await refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setImportBusy(false);
    }
  };

  if (error)
    return (
      <section className="p-6">
        <p role="alert" className="rounded bg-severity-4/20 p-3 text-severity-4">
          {error}
        </p>
      </section>
    );
  if (rows === null) return <section className="p-6">Loading…</section>;

  return (
    <section className="p-6">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">Observables</h1>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
            onClick={() => {
              const p = new URLSearchParams();
              if (filterType.trim()) p.set("data_type", filterType.trim());
              if (filterTag.trim()) p.set("tag", filterTag.trim());
              if (filterIoc) p.set("is_ioc", filterIoc);
              if (filterSighted) p.set("sighted", filterSighted);
              if (filterTlp) p.set("tlp", filterTlp);
              if (updatedWithin >= 1) p.set("updated_within_hours", String(updatedWithin));
              const qs = p.toString();
              const url = `${window.location.origin}/observables${qs ? `?${qs}` : ""}`;
              navigator.clipboard
                .writeText(url)
                .then(() => toast.success("Link copied."))
                .catch(() => toast.error("Clipboard unavailable."));
            }}
            title="Copy a link to this filtered view"
          >
            Copy URL
          </button>
          {canManage ? (
            <button
              type="button"
              className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
              onClick={() => setShowImport((v) => !v)}
            >
              {showImport ? "Cancel import" : "Import CSV"}
            </button>
          ) : null}
          <a
            href={(() => {
              const base =
                (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
                "http://localhost:8000";
              const p = new URLSearchParams();
              if (filterType.trim()) p.set("data_type", filterType.trim());
              if (filterTag.trim()) p.set("tag", filterTag.trim());
              if (filterIoc) p.set("is_ioc", filterIoc);
              if (filterSighted) p.set("sighted", filterSighted);
              if (filterTlp) p.set("tlp", filterTlp);
              const qs = p.toString();
              return `${base}/v1/observables/export-csv${qs ? `?${qs}` : ""}`;
            })()}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-md-sys-color-outline-variant px-3 py-1 text-xs hover:bg-md-sys-color-surface-container"
          >
            Export CSV
          </a>
          {canManage && selected.size > 0 ? (
            <button
              type="button"
              className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
              onClick={() => {
                void bulkMarkIoc();
              }}
              disabled={bulkBusy}
            >
              {bulkBusy ? "…" : `Mark ${selected.size} as IOC`}
            </button>
          ) : null}
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-end gap-2 text-xs">
        <label className="flex flex-col">
          <span className="text-md-sys-color-on-surface-variant">Type</span>
          <input
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1"
            placeholder="ip / domain / …"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          />
        </label>
        <label className="flex flex-col">
          <span className="text-md-sys-color-on-surface-variant">Tag</span>
          <input
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1"
            placeholder="phish, exfil, …"
            value={filterTag}
            onChange={(e) => setFilterTag(e.target.value)}
          />
        </label>
        <label className="flex flex-col">
          <span className="text-md-sys-color-on-surface-variant">IOC</span>
          <select
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1"
            value={filterIoc}
            onChange={(e) =>
              setFilterIoc(e.target.value as "" | "true" | "false")
            }
          >
            <option value="">any</option>
            <option value="true">yes</option>
            <option value="false">no</option>
          </select>
        </label>
        <label className="flex flex-col">
          <span className="text-md-sys-color-on-surface-variant">Sighted</span>
          <select
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1"
            value={filterSighted}
            onChange={(e) =>
              setFilterSighted(e.target.value as "" | "true" | "false")
            }
          >
            <option value="">any</option>
            <option value="true">yes</option>
            <option value="false">no</option>
          </select>
        </label>
        <label className="flex flex-col">
          <span className="text-md-sys-color-on-surface-variant">TLP</span>
          <select
            className="rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-1"
            value={filterTlp}
            onChange={(e) => setFilterTlp(e.target.value)}
          >
            <option value="">any</option>
            {["white", "green", "amber", "amber-strict", "red"].map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        {(filterType || filterTag || filterIoc || filterSighted || filterTlp) ? (
          <button
            type="button"
            className="rounded-full border border-md-sys-color-outline-variant px-2 py-1 text-[10px] hover:bg-md-sys-color-surface-container"
            onClick={() => {
              setFilterType("");
              setFilterTag("");
              setFilterIoc("");
              setFilterSighted("");
              setFilterTlp("");
            }}
          >
            Reset
          </button>
        ) : null}
        <span className="ml-auto text-md-sys-color-on-surface-variant">
          {rows.length} match{rows.length === 1 ? "" : "es"}
        </span>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-md-sys-color-on-surface-variant">Edited:</span>
        {(
          [
            { label: "Any", value: 0 as const },
            { label: "24h", value: 24 as const },
            { label: "7d", value: 168 as const },
            { label: "30d", value: 720 as const },
          ] satisfies { label: string; value: 0 | 24 | 168 | 720 }[]
        ).map((c) => {
          const active = updatedWithin === c.value;
          return (
            <button
              key={c.value}
              type="button"
              aria-pressed={active}
              className={`rounded-full px-2 py-0.5 text-xs ${
                active
                  ? "bg-md-sys-color-primary text-md-sys-color-on-primary"
                  : "border border-md-sys-color-outline-variant hover:bg-md-sys-color-surface-container"
              }`}
              onClick={() => setUpdatedWithin(c.value)}
            >
              {c.label}
            </button>
          );
        })}
      </div>
      {showImport && canManage ? (
        <article className="mb-4 rounded border border-md-sys-color-outline-variant p-3">
          <p className="mb-2 text-xs text-md-sys-color-on-surface-variant">
            CSV header required: data_type, data, tlp?, is_ioc?, tags?, message?
          </p>
          <textarea
            className="mb-2 w-full rounded border border-md-sys-color-outline-variant bg-md-sys-color-surface p-2 font-mono text-xs"
            rows={6}
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
          />
          <button
            type="button"
            className="rounded-full bg-md-sys-color-primary px-4 py-1 text-sm text-md-sys-color-on-primary disabled:opacity-50"
            onClick={() => {
              void importCsv();
            }}
            disabled={importBusy || !csvText.trim()}
          >
            {importBusy ? "Importing…" : "Import"}
          </button>
        </article>
      ) : null}
      {rows.length === 0 ? (
        <p className="text-md-sys-color-on-surface-variant">No observables.</p>
      ) : (
        <table className="w-full table-auto border-collapse text-sm">
          <thead>
            <tr className="border-b border-md-sys-color-outline-variant text-left">
              <th className="py-2 pr-3" />
              <th className="py-2 pr-3">Type</th>
              <th className="py-2 pr-3">Value</th>
              <th className="py-2 pr-3">TLP</th>
              <th className="py-2 pr-3">Flags</th>
              <th className="py-2 pr-3">Tags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr
                key={o.id}
                className="border-b border-md-sys-color-outline-variant/50 hover:bg-md-sys-color-surface-container"
              >
                <td className="py-2 pr-3">
                  {canManage ? (
                    <input
                      type="checkbox"
                      checked={selected.has(o.id)}
                      onChange={() => toggleOne(o.id)}
                      aria-label={`Select ${o.data}`}
                    />
                  ) : null}
                </td>
                <td className="py-2 pr-3 font-mono text-xs">
                  <Link
                    to="/observables/$observableId"
                    params={{ observableId: o.id }}
                    className="hover:underline"
                  >
                    {o.data_type}
                  </Link>
                </td>
                <td className="py-2 pr-3 break-all font-mono text-xs">
                  <Link
                    to="/observables/$observableId"
                    params={{ observableId: o.id }}
                    className="hover:underline"
                  >
                    {o.data}
                  </Link>
                </td>
                <td className="py-2 pr-3">
                  <TLPBadge tlp={o.tlp} />
                </td>
                <td className="py-2 pr-3">
                  {o.is_ioc ? (
                    <span className="mr-1 rounded-full bg-severity-4/20 px-2 py-0.5 text-xs text-severity-4">
                      IOC
                    </span>
                  ) : null}
                  {o.sighted ? (
                    <span className="rounded-full bg-severity-3/20 px-2 py-0.5 text-xs text-severity-3">
                      seen
                    </span>
                  ) : null}
                </td>
                <td className="py-2 pr-3 text-xs">{o.tags.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
