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
  assigned_firestore_user_id: string | null; // Adicionado à linha vinda da DB
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
  assignedFirestoreUserId: string | null; // Mapeado para o estado do componente
};

// Nova tipagem para os utilizadores vindos do Firestore
type FirestoreUser = {
  id: string;
  display_name: string;
  email: string;
};

const RUN_TITLE_KEYWORDS = ["cresce", "comeca", "supera"] as const;

function normalizeForMatch(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase();
}

function matchesRunsFilter(title: string): boolean {
  const normalized = normalizeForMatch(title);
  return RUN_TITLE_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

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
    assignedFirestoreUserId: row.assigned_firestore_user_id,
  };
}

export default function DashboardPage() {
  const [rows, setRows] = useState<ParsedActivity[]>([]);
  const [users, setUsers] = useState<FirestoreUser[]>([]); // Estado para utilizadores
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [memberFilter, setMemberFilter] = useState("");
  const [titleFilter, setTitleFilter] = useState("");
  const [minDistanceKm, setMinDistanceKm] = useState("");
  const [runsFilter, setRunsFilter] = useState(false);

  // Carrega tanto as atividades como os utilizadores da Supabase
  async function loadFeed() {
    setLoading(true);
    setError(null);

    try {
      const db = getSupabase();

      // 1. Puxa os utilizadores do Firestore espelhados
      const { data: userData, error: userError } = await db
        .from("users_firestore")
        .select("id, display_name, email")
        .order("display_name", { ascending: true });

      if (userError) throw new Error(userError.message);
      setUsers(userData as FirestoreUser[]);

      // 2. Puxa o Feed adicionando o novo ID de relacionamento
      const { data: feedData, error: queryError } = await db
        .from("strava_raw_feed")
        .select("id_virtual, raw_json, fetched_at, assigned_firestore_user_id")
        .order("fetched_at", { ascending: false });

      if (queryError) throw new Error(queryError.message);
      setRows((feedData as StravaRawFeedRow[]).map(parseRow));

    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadFeed();
  }, []);

  // Lógica Reativa: Quando mudas o dropdown no ecrã, atualiza o estado local temporariamente
  const handleDropdownUserChange = (idVirtual: string, selectedUserId: string) => {
    setRows((prev) =>
      prev.map((row) =>
        row.idVirtual === idVirtual
          ? { ...row, assignedFirestoreUserId: selectedUserId || null }
          : row
      )
    );
  };

  // Envia a mutação física de Update para o Postgres
  const handleSaveAssignment = async (idVirtual: string, userId: string | null) => {
    try {
      const db = getSupabase();
      const { error: updateError } = await db
        .from("strava_raw_feed")
        .update({ assigned_firestore_user_id: userId })
        .eq("id_virtual", idVirtual);

      if (updateError) {
        alert("Erro ao gravar: " + updateError.message);
      } else {
        alert("Ligação gravada com sucesso!");
        // Opcional: podes recarregar com o loadFeed() se quiseres forçar refresco total,
        // mas o estado reativo local já reflete a mudança visualmente.
      }
    } catch (e) {
      alert("Erro na ligação à base de dados.");
    }
  };

 // Algoritmo de Sugestão de Nomes Corrigido (Match por Primeiro Nome + Inicial do Apelido)
  const getSuggestedUsers = (athleteName: string) => {
    const normalizedAthlete = normalizeForMatch(athleteName).trim();
    const parts = normalizedAthlete.split(" ").filter(Boolean);
    
    if (parts.length === 0) return users;
  
    const firstNameTarget = parts[0]; // ex: "joana"
    const lastNameInitialTarget = parts[1] ? parts[1].replace(".", "")[0] : null; 
  
    return users.filter((user) => {
      const normalizedUser = normalizeForMatch(user.display_name).trim();
      const userParts = normalizedUser.split(" ").filter(Boolean);
      
      if (userParts.length === 0) return false;
  
      // CORREÇÃO AQUI: O primeiro nome do Firestore TEM de ser EXATAMENTE IGUAL ao do Strava
      const matchesFirstName = userParts[0] === firstNameTarget;
      if (!matchesFirstName) return false;
  
      // Se o Strava enviou uma inicial (ex: "A"), valida se algum dos apelidos começa por essa letra
      if (lastNameInitialTarget) {
        const userLastNames = userParts.slice(1);
        const hasMatchingLastnameInitial = userLastNames.some(name => name.startsWith(lastNameInitialTarget));
        
        return hasMatchingLastnameInitial;
      }
  
      return true;
    });
  };

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
      if (runsFilter && !matchesRunsFilter(row.title)) {
        return false;
      }
      return true;
    });
  }, [rows, memberFilter, titleFilter, minDistanceKm, runsFilter]);

  return (
    <div className="min-h-screen bg-slate-950">
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

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
            <div className="flex flex-col justify-end">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
                Runs
              </span>
              <button
                type="button"
                onClick={() => setRunsFilter((on) => !on)}
                aria-pressed={runsFilter}
                className={`rounded-lg border px-3 py-2.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-[#fc4c02]/30 ${
                  runsFilter
                    ? "border-[#fc4c02] bg-[#fc4c02]/20 text-[#fc4c02]"
                    : "border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-600"
                }`}
              >
                Cresce / Começa / Supera
              </button>
            </div>
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
                    {/* NOVA COLUNA HEADER */}
                    <Th className="pl-6">Assign App User</Th> 
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {filteredRows.map((row) => {
                    // Calcula dinamicamente as sugestões focadas para este atleta específico
                    const suggestedUsers = getSuggestedUsers(row.athleteName);

                    return (
                      <tr
                        key={row.idVirtual}
                        className={`transition-colors hover:bg-slate-800/40 ${
                          row.assignedFirestoreUserId 
                            ? "bg-green-950/5 hover:bg-green-950/10" 
                            : ""
                        }`}
                      >
                        <td className="px-4 py-3 font-medium text-white">
                          <div>
                            {row.athleteName}
                            {row.assignedFirestoreUserId && (
                              <span className="ml-2 inline-flex items-center text-[10px] text-green-400 bg-green-950 px-1.5 py-0.5 rounded border border-green-900/40">
                                Linked
                              </span>
                            )}
                          </div>
                        </td>
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
                        
                        {/* ELEMENTO TD ATUALIZADO COM TAMANHOS PADRONIZADOS */}
                          {/* COLUNA DE ATRIBUIÇÃO ADAPTATIVA */}
                        <td className="px-4 py-3 pl-6">
                          {/* CENÁRIO 1: O registo não está atribuído E não há nenhuma sugestão encontrada no Firestore */}
                          {!row.assignedFirestoreUserId && suggestedUsers.length === 0 ? (
                            <div className="w-72 flex items-center">
                              <span className="inline-flex items-center rounded-lg bg-red-950/40 px-3 py-1.5 text-xs font-semibold text-red-400 border border-red-900/30 tracking-wide">
                                ❌ Sem user no Movera
                              </span>
                            </div>
                          ) : (
                            /* CENÁRIO 2: Já está atribuído OU existem utilizadores sugeridos na lista */
                            <div className="flex items-center gap-2">
                              <select
                                value={row.assignedFirestoreUserId || ""}
                                onChange={(e) => handleDropdownUserChange(row.idVirtual, e.target.value)}
                                className={`rounded-lg border text-xs bg-slate-950 px-2 py-1.5 text-white outline-none focus:border-[#fc4c02]/50 w-52 truncate ${
                                  row.assignedFirestoreUserId 
                                    ? "border-green-800 text-green-200" 
                                    : "border-slate-700 text-slate-300"
                                }`}
                              >
                                <option value="">-- Não Atribuído --</option>
                                {suggestedUsers.map((user) => (
                                  <option key={user.id} value={user.id} className="bg-slate-950 text-white">
                                    {user.display_name}
                                  </option>
                                ))}
                              </select>
                              
                              <button
                                type="button"
                                onClick={() => handleSaveAssignment(row.idVirtual, row.assignedFirestoreUserId)}
                                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition w-16 text-center ${
                                  row.assignedFirestoreUserId
                                    ? "bg-slate-800 text-slate-400 hover:bg-slate-700 border border-slate-700 hover:text-white"
                                    : "bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold shadow-md shadow-amber-500/10"
                                }`}
                              >
                                {row.assignedFirestoreUserId ? "Mudar" : "Gravar"}
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
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
