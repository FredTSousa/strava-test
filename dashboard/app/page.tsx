"use client";
export const dynamic = "force-dynamic"; 
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
  assigned_firestore_user_id: string | null; 
  challenge_id: number | null; // 🔍 Adicionado da View
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
  assignedFirestoreUserId: string | null; 
  originalFirestoreUserId: string | null;
  challengeId: number | null;         // 🔍 Estado atual do desafio
  originalChallengeId: number | null; // 🔍 Pivot de comparação do desafio
};

type FirestoreUser = {
  id: string;
  display_name: string;
  email: string;
};

// Mapeamento estático dos desafios para renderizar as opções do dropdown
const CHALLENGES_LIST = [
  { id: 1, name: "Começa" },
  { id: 2, name: "Cresce" },
  { id: 3, name: "Supera" }
];

function normalizeForMatch(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase();
}

function formatImportDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    
    return `${day}/${month} às ${hours}:${minutes}`;
  } catch (e) {
    return "—";
  }
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
    fetchedAt: formatImportDate(row.fetched_at),
    assignedFirestoreUserId: row.assigned_firestore_user_id,
    originalFirestoreUserId: row.assigned_firestore_user_id,
    
    // Mapeia os dados relacionais do desafio
    challengeId: row.challenge_id,
    originalChallengeId: row.challenge_id,
  };
}

export default function DashboardPage() {
  const [rows, setRows] = useState<ParsedActivity[]>([]);
  const [users, setUsers] = useState<FirestoreUser[]>([]); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [memberFilter, setMemberFilter] = useState("");
  const [titleFilter, setTitleFilter] = useState("");
  const [minDistanceKm, setMinDistanceKm] = useState("");
  const [runsFilter, setRunsFilter] = useState(false);

  async function loadFeed() {
    setLoading(true);
    setError(null);
  
    try {
      const db = getSupabase();
      const { data: userData, error: userError } = await db
        .from("users_firestore")
        .select("id, display_name, email")
        .order("display_name", { ascending: true });
  
      if (userError) throw new Error(userError.message);
      setUsers(userData as FirestoreUser[]);
  
      const { data: feedData, error: queryError } = await db
        .from("view_strava_activities") 
        .select("id_virtual, raw_json, fetched_at, assigned_firestore_user_id, challenge_id") 
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

  const handleDropdownUserChange = (idVirtual: string, selectedUserId: string) => {
    setRows((prev) =>
      prev.map((row) =>
        row.idVirtual === idVirtual
          ? { ...row, assignedFirestoreUserId: selectedUserId || null }
          : row
    )
    );
  };

  // 🔍 Função gémea para escutar a mudança do Desafio no ecrã
  const handleDropdownChallengeChange = (idVirtual: string, selectedChallengeId: string) => {
    setRows((prev) =>
      prev.map((row) =>
        row.idVirtual === idVirtual
          ? { ...row, challengeId: selectedChallengeId ? Number(selectedChallengeId) : null }
          : row
      )
    );
  };

  // 🔍 O teu método UPSERT atualizado com suporte aos dois parâmetros relacionais
  const handleSaveAssignment = async (idVirtual: string, userId: string | null, challengeId: number | null) => {
    try {
      const db = getSupabase();
  
      const { error: updateError } = await db
        .from("strava_activities_metadata")
        .upsert({ 
          id_virtual: idVirtual, 
          assigned_firestore_user_id: userId || null,
          challenge_id: challengeId || null, 
          last_assign_timestamp: new Date().toISOString()
        });
  
      if (updateError) {
        alert("Erro ao gravar: " + updateError.message);
      } else {
        alert("Alterações gravadas com sucesso!");
        
        // Sincroniza ambos os pivots originais para voltar a trancar o botão
        setRows((prev) =>
          prev.map((row) =>
            row.idVirtual === idVirtual
              ? { ...row, originalFirestoreUserId: userId, originalChallengeId: challengeId }
              : row
          )
        );
      }
    } catch (e) {
      alert("Erro na ligação à base de dados.");
    }
  };

  const getSuggestedUsers = (athleteName: string) => {
    const normalizedAthlete = normalizeForMatch(athleteName).trim();
    const parts = normalizedAthlete.split(" ").filter(Boolean);
    
    if (parts.length === 0) return users;
  
    const firstNameTarget = parts[0]; 
    const lastNameInitialTarget = parts[1] ? parts[1].replace(".", "")[0] : null; 
  
    return users.filter((user) => {
      const normalizedUser = normalizeForMatch(user.display_name).trim();
      const userParts = normalizedUser.split(" ").filter(Boolean);
      
      if (userParts.length === 0) return false;
  
      const matchesFirstName = userParts[0] === firstNameTarget;
      if (!matchesFirstName) return false;
  
      if (lastNameInitialTarget) {
        const userLastNames = userParts.slice(1);
        return userLastNames.some(name => name.startsWith(lastNameInitialTarget));
      }
  
      return true;
    });
  };

  const filteredRows = useMemo(() => {
    const memberQ = memberFilter.trim().toLowerCase();
    const titleQ = titleFilter.trim().toLowerCase();
    const minKm = minDistanceKm.trim() === "" ? null : Number(minDistanceKm);

    return rows.filter((row) => {
      if (memberQ && !row.athleteName.toLowerCase().includes(memberQ)) return false;
      if (titleQ && !row.title.toLowerCase().includes(titleQ)) return false;
      if (minKm !== null && !Number.isNaN(minKm) && row.distanceKm < minKm) return false;
      
      // 🔍 Otimização: Se o botão de filtro estiver ativo, só deixa passar o que tiver um Desafio associado
      if (runsFilter && !row.challengeId) return false;
      
      return true;
    });
  }, [rows, memberFilter, titleFilter, minDistanceKm, runsFilter]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
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
                Filtrar Desafios
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
                Apenas Associadas a Desafios
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {loading && <p className="py-16 text-center text-slate-400">Loading activities…</p>}
        {error && <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-red-300">{error}</div>}

        {!loading && !error && filteredRows.length === 0 && (
          <p className="py-16 text-center text-slate-500">No activities match your filters.</p>
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
                    <Th>Importada em</Th>
                    <Th className="pl-6">Assign App User & Challenge</Th> 
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {filteredRows.map((row) => {
                    const suggestedUsers = getSuggestedUsers(row.athleteName);

                    return (
                      <tr
                        key={row.idVirtual}
                        className={`transition-colors hover:bg-slate-800/40 ${
                          row.assignedFirestoreUserId ? "bg-green-950/5 hover:bg-green-950/10" : ""
                        }`}
                      >
                        <td className="px-4 py-3 font-medium text-white">
                          <div className="flex flex-col gap-1">
                            <div className="flex items-center">
                              {row.athleteName}
                              {row.assignedFirestoreUserId && row.challengeId && (
                                <span className="ml-2 inline-flex items-center text-[10px] text-green-400 bg-green-950 px-1.5 py-0.5 rounded border border-green-900/40">
                                  Linked
                                </span>
                              )}
                            </div>
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
                        <Td className="text-slate-400 text-xs tabular-nums whitespace-nowrap">
                          {row.fetchedAt}
                        </Td>
                        <td className="px-4 py-3 pl-6">
                          {!row.assignedFirestoreUserId && suggestedUsers.length === 0 ? (
                            <div className="w-72 flex items-center">
                              <span className="inline-flex items-center rounded-lg bg-red-950/40 px-3 py-1.5 text-xs font-semibold text-red-400 border border-red-900/30 tracking-wide">
                                ❌ Sem user no Movera
                              </span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-3">
                              {/* DROPDOWN 1: Membros Movera */}
                              <select
                                value={row.assignedFirestoreUserId || ""}
                                onChange={(e) => handleDropdownUserChange(row.idVirtual, e.target.value)}
                                className={`rounded-lg border text-xs bg-slate-950 px-2 py-1.5 text-white outline-none focus:border-[#fc4c02]/50 w-44 truncate ${
                                  row.assignedFirestoreUserId ? "border-green-800 text-green-200" : "border-slate-700 text-slate-300"
                                }`}
                              >
                                <option value="">-- Não Atribuído --</option>
                                {(() => {
                                  const finalOptions = [...suggestedUsers];
                                  
                                  if (row.assignedFirestoreUserId) {
                                    const isAlreadyInOptions = finalOptions.some(u => u.id === row.assignedFirestoreUserId);
                                    if (!isAlreadyInOptions) {
                                      const currentUserObj = users.find(u => u.id === row.assignedFirestoreUserId);
                                      if (currentUserObj) finalOptions.push(currentUserObj);
                                    }
                                  }
                                  
                                  return finalOptions.map((user) => (
                                    <option key={user.id} value={user.id} className="bg-slate-950 text-white">
                                      {user.display_name}
                                    </option>
                                  ));
                                })()}
                              </select>

                              {/* 🔍 DROPDOWN 2: Tabela Relacional de Desafios (Challenges) */}
                              <select
                                value={row.challengeId || ""}
                                onChange={(e) => handleDropdownChallengeChange(row.idVirtual, e.target.value)}
                                className={`rounded-lg border text-xs bg-slate-950 px-2 py-1.5 text-white outline-none focus:border-[#fc4c02]/50 w-32 ${
                                  row.challengeId ? "border-amber-700 text-amber-200" : "border-slate-700 text-slate-300"
                                }`}
                              >
                                <option value="">-- Sem Desafio --</option>
                                {CHALLENGES_LIST.map((challenge) => (
                                  <option key={challenge.id} value={challenge.id} className="bg-slate-950 text-white">
                                    {challenge.name}
                                  </option>
                                ))}
                              </select>
                              
                              {/* BOTÃO GRAVAR: Escuta e valida ambos os dropdowns simultaneamente */}
                              {(() => {
                                const hasUserChanged = (row.assignedFirestoreUserId || "") !== (row.originalFirestoreUserId || "");
                                const hasChallengeChanged = (row.challengeId || 0) !== (row.originalChallengeId || 0);
                                const hasChanges = hasUserChanged || hasChallengeChanged;

                                return (
                                  <button
                                    type="button"
                                    disabled={!hasChanges}
                                    onClick={() => handleSaveAssignment(row.idVirtual, row.assignedFirestoreUserId, row.challengeId)}
                                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition w-16 text-center ${
                                      hasChanges
                                        ? "bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold shadow-md shadow-amber-500/10 cursor-pointer"
                                        : "bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed opacity-50"
                                    }`}
                                  >
                                    Gravar
                                  </button>
                                );
                              })()}
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

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th scope="col" className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 ${className}`}>
      {children}
    </th>
  );
}

function Td({ children, className = "", title }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <td className={`px-4 py-3 ${className}`} title={title}>
      {children}
    </td>
  );
}
