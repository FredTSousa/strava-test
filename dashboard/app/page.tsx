"use client";
export const dynamic = "force-dynamic"; 
import { useEffect, useMemo, useState } from "react";
import { getSupabase } from "./utils/supabase";

type StravaAthlete = {
  id?: number; 
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
  device_name?: string;
};

type StravaRawFeedRow = {
  id_virtual: string;
  raw_json: StravaActivityJson;
  fetched_at: string;
  assigned_firestore_user_id: string | null; 
  synced_to_firestore: boolean;
  total_strava_club_matches?: number;
  firestore_user_athlete_id?: number | null;
  activity_clube_id?: number | null; 
};

type ParsedActivity = {
  idVirtual: string;
  athleteIdFromStrava: number | null; 
  athleteName: string;
  deviceName: string;
  title: string;
  sportType: string;
  distanceKm: number;
  movingTimeMin: number;
  elevationGain: number;
  fetchedAt: string; 
  assignedFirestoreUserId: string | null; 
  isSynced: boolean;
  totalStravaClubMatches: number;
  hasActivityClube: boolean; 
  firestoreUserAthleteId: number | null;
};

type FirestoreUser = {
  id: string;
  display_name: string;
  email: string;
  athlete_id: number | null; 
};

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
    athleteIdFromStrava: athlete.id ? Number(athlete.id) : null,
    athleteName,
    deviceName: raw.device_name ?? "Unknown Device",
    title: raw.name ?? "Untitled",
    sportType: raw.sport_type ?? "—",
    distanceKm: Math.round((distanceM / 1000) * 100) / 100,
    movingTimeMin: Math.round(movingSec / 60),
    elevationGain: Math.round(raw.total_elevation_gain ?? 0),
    fetchedAt: formatImportDate(row.fetched_at),
    assignedFirestoreUserId: row.assigned_firestore_user_id, 
    isSynced: row.synced_to_firestore ?? false,
    totalStravaClubMatches: row.total_strava_club_matches ?? 0,
    hasActivityClube: row.activity_clube_id !== null && row.activity_clube_id !== undefined, 
    firestoreUserAthleteId: row.firestore_user_athlete_id ?? null,
  };
}

function LoginPage({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);

    try {
      const db = getSupabase();
      const { error } = await db.auth.signInWithPassword({ email, password });
      if (error) throw error;
      onLoginSuccess();
    } catch (err: any) {
      setAuthError(err.message || "Erro no Login.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-slate-950 p-4 text-slate-100">
      <form onSubmit={handleLogin} className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-2xl backdrop-blur">
        <div className="text-center mb-6">
          <p className="text-xs font-medium uppercase tracking-wider text-[#fc4c02]">Movera Run Club</p>
          <h2 className="text-xl font-bold text-white mt-1">Admin Dashboard</h2>
        </div>
        {authError && <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-400">{authError}</div>}
        <div className="mb-4">
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600 outline-none focus:border-[#fc4c02]/50" />
        </div>
        <div className="mb-6">
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600 outline-none focus:border-[#fc4c02]/50" />
        </div>
        <button type="submit" disabled={authLoading} className="w-full rounded-lg bg-[#fc4c02] py-2 text-sm font-bold text-white hover:bg-[#e04302] transition disabled:opacity-50">
          {authLoading ? "A verificar..." : "Entrar no Painel"}
        </button>
      </form>
    </div>
  );
}

export default function DashboardPage() {
  const [session, setSession] = useState<any>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  const [rows, setRows] = useState<ParsedActivity[]>([]);
  const [users, setUsers] = useState<FirestoreUser[]>([]); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [memberFilter, setMemberFilter] = useState("");
  const [titleFilter, setTitleFilter] = useState("");
  const [minDistanceKm, setMinDistanceKm] = useState("");
  const [runsFilter, setRunsFilter] = useState(false);
  
  const [unassignedOnlyFilter, setUnassignedOnlyFilter] = useState(false); 
  const [noMoveraUserFilter, setNoMoveraUserFilter] = useState(false);

  // 📱 Estado para abrir/fechar os filtros no telemóvel
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  async function loadFeed() {
    setLoading(true);
    setError(null);
  
    try {
      const db = getSupabase();
      const { data: userData, error: userError } = await db
        .from("users_firestore")
        .select("id, display_name, email, athlete_id")
        .order("display_name", { ascending: true });
  
      if (userError) throw new Error(userError.message);
      
      const usersMap = (userData as FirestoreUser[]).reduce((acc, user) => {
        acc[user.id] = { ...user };
        return acc;
      }, {} as Record<string, FirestoreUser>);
  
      const { data: feedData, error: queryError } = await db
        .from("view_strava_activities") 
        .select("id_virtual, raw_json, fetched_at, assigned_firestore_user_id, synced_to_firestore, total_strava_club_matches, firestore_user_athlete_id, activity_clube_id") 
        .order("fetched_at", { ascending: false });
  
      if (queryError) throw new Error(queryError.message);
      
      const rawRows = feedData as StravaRawFeedRow[];
      
      rawRows.forEach(row => {
        if (row.assigned_firestore_user_id && row.firestore_user_athlete_id && usersMap[row.assigned_firestore_user_id]) {
          usersMap[row.assigned_firestore_user_id].athlete_id = row.firestore_user_athlete_id;
        }
      });
      
      setUsers(Object.values(usersMap));
      setRows(rawRows.map(parseRow));
  
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const db = getSupabase();

    db.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setCheckingAuth(false);
      if (session) loadFeed();
    });

    const { data: { subscription } } = db.auth.onAuthStateChange((_event, currentSession) => {
      setSession(currentSession);
      if (currentSession) loadFeed();
    });

    return () => subscription.unsubscribe();
  }, []);

  const handleLogout = async () => {
    setLoading(true);
    const db = getSupabase();
    await db.auth.signOut();
    setSession(null);
    setRows([]);
    setUsers([]);
    setLoading(false);
  };

  const handleDropdownUserChange = async (idVirtual: string, selectedUserId: string) => {
    const valueToSave = selectedUserId || null;

    console.log("=== 🚀 INÍCIO DO ASSIGN MANUAL ===");

    const currentActivity = rows.find(r => r.idVirtual === idVirtual);
    const realStravaAthleteId = currentActivity?.firestoreUserAthleteId ?? null;

    console.log("Nome do Atleta da linha:", currentActivity?.athleteName);
    console.log("ID do Strava resgatado da View (atividades_clube):", realStravaAthleteId);
    console.log("ID do Utilizador Firestore para associar:", valueToSave);

    setRows((prev) =>
      prev.map((row) =>
        row.idVirtual === idVirtual
          ? { ...row, assignedFirestoreUserId: valueToSave }
          : row
      )
    );

    if (valueToSave && realStravaAthleteId) {
      setUsers((prevUsers) =>
        prevUsers.map((u) =>
          u.id === valueToSave ? { ...u, athlete_id: realStravaAthleteId } : u
        )
      );
    }

    try {
      const db = getSupabase();
      console.log("📡 A enviar UPSERT para 'strava_activities_metadata'...");
      const { error: updateError } = await db
        .from("strava_activities_metadata")
        .upsert({ 
          id_virtual: idVirtual, 
          assigned_firestore_user_id: valueToSave,
          synced_to_firestore: false, 
          last_assign_timestamp: new Date().toISOString()
        });

      if (updateError) throw updateError;

      if (valueToSave && realStravaAthleteId) {
        console.log(`📡 A enviar UPDATE para 'users_firestore' -> set athlete_id = ${realStravaAthleteId} onde id = '${valueToSave}'`);
        const { data, error: userUpdateError, status } = await db
          .from("users_firestore")
          .update({ athlete_id: realStravaAthleteId })
          .eq("id", valueToSave)
          .select();

        if (userUpdateError) {
          console.error("❌ Erro ao atualizar athlete_id em 'users_firestore':", userUpdateError);
        } else {
          console.log(`🟢 SUCESSO NA BD! O utilizador ganhou o ID do Strava. Status HTTP: ${status}`, data);
        }
      } else {
        console.warn("🚫 O UPDATE no utilizador foi ignorado porque o realStravaAthleteId está a null.");
      }

    } catch (e) {
      console.error("💥 Erro crítico no catch:", e);
      alert("Erro ao gravar os dados na base de dados.");
      loadFeed();
    }
    console.log("=== 🏁 FIM DO ASSIGN MANUAL ===");
  };

  const getSuggestedUsers = (athleteName: string) => {
    const normalizeAthlete = normalizeForMatch(athleteName).trim();
    const parts = normalizeAthlete.split(" ").filter(Boolean);
    if (parts.length === 0) return users;
    const firstNameTarget = parts[0]; 
    const lastNamePart = parts[parts.length - 1];
    const lastNameInitialTarget = lastNamePart ? lastNamePart.replace(".", "")[0] : null; 
    return users.filter((user) => {
      const normalizedUser = normalizeForMatch(user.display_name).trim();
      const userParts = normalizedUser.split(" ").filter(Boolean);
      if (userParts.length === 0) return false;
      const matchesFirstName = userParts[0] === firstNameTarget;
      if (!matchesFirstName) return false;
      if (lastNameInitialTarget && userParts.length > 1) {
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
      const hasUserChosen = !!row.assignedFirestoreUserId;
      const suggestedUsers = getSuggestedUsers(row.athleteName);
      const isMissingMoveraUser = !hasUserChosen && suggestedUsers.length === 0;

      if (unassignedOnlyFilter && (hasUserChosen || row.isSynced || isMissingMoveraUser)) {
        return false;
      }

      if (noMoveraUserFilter && !isMissingMoveraUser) return false;

      if (memberQ && !row.athleteName.toLowerCase().includes(memberQ)) return false;
      if (titleQ && !row.title.toLowerCase().includes(titleQ)) return false;
      if (minKm !== null && !Number.isNaN(minKm) && row.distanceKm < minKm) return false;
      
      if (runsFilter) {
        const normalizedTitle = normalizeForMatch(row.title);
        const hasChallengeInName = normalizedTitle.includes("comeca") || 
                                   normalizedTitle.includes("cresce") || 
                                   normalizedTitle.includes("supera") ||
                                   normalizedTitle.includes("desafio") || 
                                   normalizedTitle.includes("movera");

        if (!hasChallengeInName) return false;
      }
      return true;
    });
  }, [rows, memberFilter, titleFilter, minDistanceKm, runsFilter, unassignedOnlyFilter, noMoveraUserFilter]);

  if (checkingAuth) {
    return <div className="h-screen w-screen flex items-center justify-center bg-slate-950 text-slate-400 text-sm">A verificar sessão...</div>;
  }

  if (!session) {
    return <LoginPage onLoginSuccess={() => loadFeed()} />;
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur shrink-0">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:py-6 sm:px-6 lg:px-8">
          
          {/* Topo do Header: Título e Botões Responsivos */}
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <p className="text-sm font-medium uppercase tracking-wider text-[#fc4c02]">
                Strava Club
              </p>
              <h1 className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-white">
                Activity Feed
              </h1>
              <p className="mt-1 text-xs text-slate-400 hidden sm:block">
                Live view of synced club activities from Supabase
              </p>
            </div>

            <div className="flex items-center justify-between sm:justify-end gap-3 w-full sm:w-auto border-t border-slate-800/60 pt-3 sm:pt-0 sm:border-none">
              <button
                onClick={handleLogout}
                className="rounded-lg border border-slate-700 hover:border-red-500/40 hover:text-red-400 bg-slate-950 px-3 py-1.5 text-xs font-medium transition focus:outline-none"
              >
                Terminar Sessão 🚪
              </button>

              <div className="rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-1.5 text-xs text-slate-300">
                <span className="font-semibold text-[#fc4c02]">{filteredRows.length}</span>
                <span className="text-slate-500"> / </span>
                <span>{rows.length}</span>
                <span className="ml-1 text-slate-500 hidden sm:inline">activities</span>
              </div>
            </div>
          </div>

          {/* 📱 Botão Compressível de Filtros visível apenas em Mobile */}
          <button 
            type="button"
            onClick={() => setMobileFiltersOpen(!mobileFiltersOpen)}
            className="flex items-center justify-center gap-2 w-full lg:hidden rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:bg-slate-900 focus:outline-none"
          >
            {mobileFiltersOpen ? "Ocultar Painel de Filtros ▴" : "Filtrar Resultados ⚙️ ▾"}
          </button>

          {/* Zona de Filtros: Grelha nativa PC / Colapsável em Mobile */}
          <div className={`${mobileFiltersOpen ? "block" : "hidden"} lg:block mt-1 lg:mt-0`}>
            <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 bg-slate-900/40 lg:bg-transparent p-3 lg:p-0 rounded-xl border border-slate-850 lg:border-none">
              <FilterField id="member" label="Member Name" placeholder="Search athlete…" value={memberFilter} onChange={setMemberFilter} />
              <FilterField id="title" label="Title Keyword" placeholder="Search activity title…" value={titleFilter} onChange={setTitleFilter} />
              <FilterField id="distance" label="Minimum Distance (km)" placeholder="e.g. 5" type="number" min={0} step="0.1" value={minDistanceKm} onChange={setMinDistanceKm} />
              
              <div className="flex flex-col justify-end">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">Filtrar Desafios</span>
                <button type="button" onClick={() => setRunsFilter((on) => !on)} aria-pressed={runsFilter} className={`rounded-lg border px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-[#fc4c02]/30 truncate ${runsFilter ? "border-[#fc4c02] bg-[#fc4c02]/20 text-[#fc4c02]" : "border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-600"}`}>Prováveis Desafios</button>
              </div>
              <div className="flex flex-col justify-end">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">Falta Tratar</span>
                <button type="button" onClick={() => setUnassignedOnlyFilter((on) => !on)} aria-pressed={unassignedOnlyFilter} className={`rounded-lg border px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-amber-500/30 truncate ${unassignedOnlyFilter ? "border-amber-500 bg-amber-500/20 text-amber-400 font-semibold" : "border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-600"}`}>Por Escolher</button>
              </div>
              <div className="flex flex-col justify-end">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">Incompatíveis</span>
                <button type="button" onClick={() => setNoMoveraUserFilter((on) => !on)} aria-pressed={noMoveraUserFilter} className={`rounded-lg border px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-red-500/30 truncate ${noMoveraUserFilter ? "border-red-500 bg-red-500/20 text-red-400 font-semibold" : "border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-600"}`}>Sem User Movera</button>
              </div>
            </div>
          </div>

        </div>
      </header>

      {/* Tabela de Dados: Invólucro com overflow isolado anti-quebra */}
      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-4 sm:py-6 sm:px-6 lg:px-8 min-h-0 flex flex-col">
        {loading && <p className="py-16 text-center text-slate-400">Loading activities…</p>}
        {error && <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-red-300">{error}</div>}

        {!loading && !error && filteredRows.length === 0 && <p className="py-16 text-center text-slate-500">No activities match your filters.</p>}

        {!loading && !error && filteredRows.length > 0 && (
          <div className="flex-1 flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/50 shadow-xl shadow-black/20 min-h-0">
            {/* 🟢 O TRUQUE MOBILE: overflow-x-auto permite arrastar horizontalmente em ecrãs pequenos sem partir o dashboard */}
            <div className="flex-1 overflow-auto min-h-0 universal-scrollbar">
              <table className="min-w-[1050px] lg:min-w-full divide-y divide-slate-800 text-left text-sm table-fixed">
                <colgroup>
                  <col className="w-[160px]" />
                  <col className="w-auto" />
                  <col className="w-[80px]" />
                  <col className="w-[95px]" />
                  <col className="w-[100px]" />
                  <col className="w-[85px]" />
                  <col className="w-[130px]" />
                  <col className="w-[190px]" />
                </colgroup>
                <thead className="sticky top-0 z-10 bg-slate-900 shadow-md">
                  <tr className="border-b border-slate-800">
                    <Th>Athlete / Device</Th>
                    <Th>Activity</Th>
                    <Th>Sport</Th>
                    <Th className="text-right">Distance</Th>
                    <Th className="text-right">Moving Time</Th>
                    <Th className="text-right">Eleva.</Th>
                    <Th>Importada em</Th>
                    <Th className="pl-6 pr-4">Assign App User</Th> 
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 bg-slate-900/20">
                  {filteredRows.map((row) => {
                    const suggestedUsers = getSuggestedUsers(row.athleteName);
                    const hasUser = !!row.assignedFirestoreUserId;
                    const associadoAoUser = users.find(u => u.id === row.assignedFirestoreUserId);
                    const targetAthleteId = row.firestoreUserAthleteId || associadoAoUser?.athlete_id || null;

                    return (
                      <tr key={row.idVirtual} className={`transition-colors hover:bg-slate-800/40 ${row.isSynced ? "bg-emerald-950/5" : "bg-slate-950"}`}>
                        <td className="px-4 py-3 font-medium text-white align-top">
                          <div className="flex flex-col gap-0.5">
                            <div className="whitespace-normal break-words leading-tight text-xs max-w-[142px]">
                              {row.hasActivityClube && targetAthleteId ? (
                                <a href={`https://www.strava.com/athletes/${targetAthleteId}`} target="_blank" rel="noopener noreferrer" className="text-[#fc4c02] hover:underline font-semibold inline-flex items-center gap-1" title="Ver atleta no Strava Club">
                                  {row.athleteName}
                                  <span className="text-[10px] text-slate-500">🔗</span>
                                </a>
                              ) : (
                                <span className="text-slate-400">{row.athleteName}</span>
                              )}
                            </div>
                            <div className="text-slate-500 text-[10px] truncate max-w-[142px]" title={row.deviceName}>{row.deviceName}</div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-slate-200 whitespace-normal break-words leading-normal align-top">{row.title}</td>
                        <td className="px-4 py-2.5 align-top">
                          <span className="inline-flex rounded-full bg-[#fc4c02]/15 px-1.5 py-0.5 text-[11px] font-medium text-[#fc4c02]">{row.sportType}</span>
                        </td>
                        <Td className="text-right tabular-nums text-slate-300 align-top">{row.distanceKm.toFixed(2)} km</Td>
                        <Td className="text-right tabular-nums text-slate-300 align-top">{row.movingTimeMin} min</Td>
                        <Td className="text-right tabular-nums text-slate-300 align-top">{row.elevationGain} m</Td>
                        <Td className="text-slate-400 text-xs tabular-nums whitespace-nowrap align-top">{row.fetchedAt}</Td>
                        <td className="px-4 py-3 pl-6 pr-4 align-top">
                          {row.isSynced ? (
                            <div className="flex items-center"><span className="inline-flex items-center rounded-lg bg-emerald-950/80 px-3 py-1.5 text-xs font-bold text-emerald-400 border border-emerald-500/30 tracking-wide whitespace-nowrap">✓ Sincronizado</span></div>
                          ) : !hasUser && Math.max(suggestedUsers.length, 0) === 0 ? (
                            <div className="flex items-center"><span className="inline-flex items-center rounded-lg bg-red-950/40 px-3 py-1.5 text-xs font-semibold text-red-400 border border-red-900/30 tracking-wide whitespace-nowrap">❌ Sem user no Movera</span></div>
                          ) : (
                            <div className="flex items-center max-w-[170px]">
                              <select
                                value={row.assignedFirestoreUserId || ""}
                                onChange={(e) => handleDropdownUserChange(row.idVirtual, e.target.value)}
                                className={`rounded-lg border text-xs bg-slate-950 px-2 py-1.5 text-slate-200 outline-none focus:border-[#fc4c02]/50 w-full truncate transition-all duration-200 ${!hasUser ? "border-amber-500/80 text-amber-400 font-bold bg-amber-950/30 shadow-md shadow-amber-500/10" : "border-slate-700 text-slate-200 hover:border-slate-600"}`}
                              >
                                <option value="" className="text-amber-400 font-bold">-- Escolher User --</option>
                                {(() => {
                                  const semContaCount = row.totalStravaClubMatches - suggestedUsers.length;
                                  if (semContaCount > 0) {
                                    return <option disabled className="text-red-400 bg-red-950/40 font-semibold">⚠️ Há mais {semContaCount} {semContaCount === 1 ? "membro" : "membros"} {row.athleteName} sem conta no Movera!</option>;
                                  }
                                  return null;
                                })()}
                               {suggestedUsers.length > 0 && (
                                <optgroup label="✨ Utilizadores Encontrados" className="bg-slate-900 text-[#fc4c02] font-semibold">
                                  {suggestedUsers
                                    .filter((user) => {
                                      if (user.athlete_id === null || user.athlete_id === undefined) return true;
                                      return Number(user.athlete_id) === Number(row.firestoreUserAthleteId);
                                    })
                                    .map((user) => {
                                      const hasIdLinked = user.athlete_id !== null;
                                      return <option key={`sug-${user.id}`} value={user.id} className="bg-slate-950 text-white font-normal">{hasIdLinked ? "🆔 " : "⬜ "} {user.display_name} ({user.email})</option>;
                                    })}
                                </optgroup>
                              )}
                              </select>
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

function FilterField({ id, label, value, onChange, placeholder, type = "text", min, step }: { id: string; label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string; min?: number; step?: string; }) {
  return (
    <label htmlFor={id} className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      <input id={id} type={type} min={min} step={step} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600 outline-none transition focus:border-[#fc4c02]/50 focus:ring-2 focus:ring-[#fc4c02]/30" />
    </label>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <th scope="col" className={`px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-400 ${className}`}>{children}</th>;
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 ${className}`}>{children}</td>;
}
