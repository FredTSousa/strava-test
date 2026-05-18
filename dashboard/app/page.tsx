"use client";

import { useEffect, useMemo, useState } from "react";
import { getSupabase } from "./utils/supabase";

type StravaAthlete = {
  firstname?: string;
  lastname?: string;
};

type StravaActivityJson = {
  name?: string;
  sport_type?: string;
  distance?: number;
  moving_time?: number;
  total_elevation_gain?: number;
  athlete?: StravaAthlete;
};

type StravaRawFeedRow = {
  id_virtual: string;
  raw_json: StravaActivityJson;
  fetched_at: string;
};

type ParsedActivity = {
  idVirtual: string;
  athleteName: string;
  title: string;
  sportType: string;
  distanceKm: number;
  movingTimeMin: number;
  elevationGain: number;
  fetchedAt: string;
};

function parseRow(row: StravaRawFeedRow): ParsedActivity {
  const raw = row.raw_json ?? {};
  const athlete = raw.athlete ?? {};
  const first = (athlete.firstname ?? "").trim();
  const last = (athlete.lastname ?? "").trim();
  const athleteName = [first, last].filter(Boolean).join(" ") || "Unknown";

  const distanceM = raw.distance ?? 0;
  const movingSec = raw.moving_time ?? 0;

  return {
    idVirtual: row.id_virtual,
    athleteName,
    title: raw.name ?? "Untitled",
    sportType: raw.sport_type ?? "—",
    distanceKm: Math.round((distanceM / 1000) * 100) / 100,
    movingTimeMin: Math.round(movingSec / 60),
    elevationGain: Math.round(raw.total_elevation_gain ?? 0),
    fetchedAt: row.fetched_at,
  };
}

export default function DashboardPage() {
  const [rows, setRows] = useState<ParsedActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [memberFilter, setMemberFilter] = useState("");
  const [titleFilter, setTitleFilter] = useState("");
  const [minDistanceKm, setMinDistanceKm] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadFeed() {
      setLoading(true);
      setError(null);

      let db;
      try {
        db = getSupabase();
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
        return;
      }

      const { data, error: queryError } = await db
        .from("strava_raw_feed")
        .select("id_virtual, raw_json, fetched_at")
        .order("fetched_at", { ascending: false });

      if (cancelled) return;

      if (queryError) {
        setError(queryError.message);
        setRows([]);
      } else {
        setRows((data as StravaRawFeedRow[]).map(parseRow));
      }

      setLoading(false);
    }

    loadFeed();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredRows = useMemo(() => {
    const memberQ = memberFilter.trim().toLowerCase();
    const titleQ = titleFilter.trim().toLowerCase();
    const minKm = minDistanceKm.trim() === "" ? null : Number(minDistanceKm);

    return rows.filter((row) => {
      if (memberQ && !row.athleteName.toLowerCase().includes(memberQ)) {
        return false;
      }
      if (titleQ && !row.title.toLowerCase().includes(titleQ)) {
        return false;
      }
      if (minKm !== null && !Number.isNaN(minKm) && row.distanceKm < minKm) {
        return false;
      }
      return true;
    });
  }, [rows, memberFilter, titleFilter, minDistanceKm]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-medium uppercase tracking-wider text-[#fc4c02]">
                Strava Club
              </p>
              <h1 className="mt-1 text-3xl font-bold tracking-tight text-white">
                Activity Feed
              </h1>
              <p className="mt-2 text-slate-400">
                Live view of synced club activities from Supabase
              </p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2 text-sm text-slate-300">
              <span className="font-semibold text-[#fc4c02]">{filteredRows.length}</span>
              <span className="text-slate-500"> / </span>
              <span>{rows.length}</span>
              <span className="ml-1 text-slate-500">activities</span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <FilterField
              id="member"
              label="Member Name"
              placeholder="Search athlete…"
              value={memberFilter}
              onChange={setMemberFilter}
            />
            <FilterField
              id="title"
              label="Title Keyword"
              placeholder="Search activity title…"
              value={titleFilter}
              onChange={setTitleFilter}
            />
            <FilterField
              id="distance"
              label="Minimum Distance (km)"
              placeholder="e.g. 5"
              type="number"
              min={0}
              step="0.1"
              value={minDistanceKm}
              onChange={setMinDistanceKm}
            />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {loading && (
          <p className="py-16 text-center text-slate-400">Loading activities…</p>
        )}

        {error && (
          <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-red-300">
            {error}
          </div>
        )}

        {!loading && !error && filteredRows.length === 0 && (
          <p className="py-16 text-center text-slate-500">
            No activities match your filters.
          </p>
        )}

        {!loading && !error && filteredRows.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/50 shadow-xl shadow-black/20">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-800 text-left text-sm">
                <thead>
                  <tr className="bg-slate-800/80">
                    <Th>Athlete</Th>
                    <Th>Activity</Th>
                    <Th>Sport</Th>
                    <Th className="text-right">Distance</Th>
                    <Th className="text-right">Moving Time</Th>
                    <Th className="text-right">Elevation</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {filteredRows.map((row) => (
                    <tr
                      key={row.idVirtual}
                      className="transition-colors hover:bg-slate-800/40"
                    >
                      <Td className="font-medium text-white">{row.athleteName}</Td>
                      <Td className="max-w-xs truncate text-slate-200" title={row.title}>
                        {row.title}
                      </Td>
                      <Td>
                        <span className="inline-flex rounded-full bg-[#fc4c02]/15 px-2.5 py-0.5 text-xs font-medium text-[#fc4c02]">
                          {row.sportType}
                        </span>
                      </Td>
                      <Td className="text-right tabular-nums text-slate-300">
                        {row.distanceKm.toFixed(2)} km
                      </Td>
                      <Td className="text-right tabular-nums text-slate-300">
                        {row.movingTimeMin} min
                      </Td>
                      <Td className="text-right tabular-nums text-slate-300">
                        {row.elevationGain} m
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function FilterField({
  id,
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  min,
  step,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  min?: number;
  step?: string;
}) {
  return (
    <label htmlFor={id} className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <input
        id={id}
        type={type}
        min={min}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white placeholder:text-slate-600 outline-none transition focus:border-[#fc4c02]/50 focus:ring-2 focus:ring-[#fc4c02]/30"
      />
    </label>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 ${className}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  className = "",
  title,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <td className={`px-4 py-3 ${className}`} title={title}>
      {children}
    </td>
  );
}
