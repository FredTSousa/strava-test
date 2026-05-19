"use client";

import { useEffect, useState } from "react";
import { getSupabase } from "../utils/supabase";

type StravaRawFeedRow = {
  id_virtual: string;
  raw_json: {
    name?: string;
    distance?: number;
    athlete?: { firstname?: string; lastname?: string };
  };
};

type UnassignedActivity = {
  idVirtual: string;
  title: string;
  athleteName: string;
  distanceKm: number;
};

type MemberOption = {
  id: number;
  nome_completo: string;
  keyword: string | null;
};

export default function ActivitiesCuratorPage() {
  const [activities, setActivities] = useState<UnassignedActivity[]>([]);
  const [members, setMembers] = useState<MemberOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadCuratorData() {
    setLoading(true);
    setError(null);
    try {
      const db = getSupabase();

      // Aggregate manual: junta treinos órfãos + membros em memória
      const { data: actsData, error: actsErr } = await db
        .from("strava_raw_feed")
        .select("id_virtual, raw_json")
        .is("assigned_member_id", null);

      const { data: membsData, error: membsErr } = await db
        .from("club_members")
        .select("id, nome_completo, keyword");

      if (actsErr || membsErr) {
        setError(actsErr?.message || membsErr?.message || "Query Error");
        return;
      }

      if (actsData) {
        const parsed = (actsData as StravaRawFeedRow[]).map((row) => {
          const raw = row.raw_json ?? {};
          const ath = raw.athlete ?? {};
          const name = [ath.firstname ?? "", ath.lastname ?? ""].filter(Boolean).join(" ").trim() || "Unknown";
          return {
            idVirtual: row.id_virtual,
            title: raw.name ?? "Untitled",
            athleteName: name,
            distanceKm: Math.round(((raw.distance ?? 0) / 1000) * 100) / 100,
          };
        });
        setActivities(parsed);
      }

      if (membsData) setMembers(membsData as MemberOption[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCuratorData();
  }, []);

  const handleAssign = async (idVirtual: string, memberId: number) => {
    try {
      const db = getSupabase();
      const { error: updateError } = await db
        .from("strava_raw_feed")
        .update({ assigned_member_id: memberId })
        .eq("id_virtual", idVirtual);

      if (!updateError) {
        // Ajax-refresh local instantâneo
        setActivities((prev) => prev.filter((a) => a.idVirtual !== idVirtual));
      } else {
        alert("Assignment error: " + updateError.message);
      }
    } catch (e) {
      alert("Connection failure");
    }
  };

  return (
    <div className="min-h-screen text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          <p className="text-sm font-medium uppercase tracking-wider text-[#fc4c02]">
            Data Integrity
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-white">
            Activity Curator
          </h1>
          <p className="mt-2 text-slate-400">
            Resolve identity ambiguities by pinning raw Strava logs to clean member IDs
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {loading && <p className="text-center text-slate-400 py-12">Checking log queue…</p>}
        {error && <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-red-300 mb-6">{error}</div>}

        {!loading && !error && activities.length === 0 && (
          <div className="rounded-xl border border-green-900/30 bg-green-950/20 p-6 text-center text-green-400 font-medium">
            ✓ Integrity clear! All synced incoming workouts have been cleanly matched to members.
          </div>
        )}

        {!loading && !error && activities.length > 0 && (
          <div className="flex flex-col gap-6">
            {activities.map((act) => {
              // Procura os possíveis clones guardados que têm este exato texto
              const possibleClones = members.filter((m) => m.nome_completo.toLowerCase() === act.athleteName.toLowerCase());

              return (
                <div key={act.idVirtual} className="rounded-xl border border-slate-800 bg-slate-900/30 p-6 shadow-md">
                  <div className="mb-4">
                    <h3 className="text-lg font-bold text-slate-200">{act.title}</h3>
                    <p className="text-sm text-slate-400 mt-1">
                      Logged Name: <span className="text-white font-medium">{act.athleteName}</span> | Distance: <span className="text-[#fc4c02] font-semibold">{act.distanceKm.toFixed(2)} km</span>
                    </p>
                  </div>

                  <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
                    <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
                      Assign activity to:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {possibleClones.length === 0 ? (
                        <span className="text-sm text-red-400">⚠️ No match found in Member base. Run synchronization.</span>
                      ) : (
                        possibleClones.map((membro) => (
                          <button
                            key={membro.id}
                            type="button"
                            onClick={() => handleAssign(act.idVirtual, membro.id)}
                            className="rounded-lg bg-[#fc4c02]/10 hover:bg-[#fc4c02]/20 border border-[#fc4c02]/30 text-[#fc4c02] px-3 py-2 text-sm font-medium transition"
                          >
                            {membro.nome_completo} {membro.keyword ? `(${membro.keyword})` : ""}
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
