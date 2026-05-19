"use client";

import { useEffect, useState } from "react";
import { getSupabase } from "../utils/supabase";

type Member = {
  id: number;
  firstname: string;
  lastname: string;
  nome_completo: string;
  keyword: string | null;
  is_validated: boolean;
};

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadMembers() {
    setLoading(true);
    setError(null);
    try {
      const db = getSupabase();
      const { data, error: queryError } = await db
        .from("club_members")
        .select("*")
        .order("nome_completo", { ascending: true });

      if (queryError) {
        setError(queryError.message);
      } else if (data) {
        setMembers(data as Member[]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMembers();
  }, []);

  const handleKeywordChange = (id: number, newKeyword: string) => {
    setMembers((prev) =>
      prev.map((m) => (m.id === id ? { ...m, keyword: newKeyword } : m))
    );
  };

  const handleValidate = async (id: number, keyword: string | null) => {
    try {
      const db = getSupabase();
      const { error: updateError } = await db
        .from("club_members")
        .update({ keyword, is_validated: true })
        .eq("id", id);

      if (updateError) {
        alert("Error saving: " + updateError.message);
      } else {
        loadMembers(); // Refresh implícito
      }
    } catch (e) {
      alert("Database connection error");
    }
  };

  return (
    <div className="min-h-screen text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          <p className="text-sm font-medium uppercase tracking-wider text-[#fc4c02]">
            Management
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-white">
            Club Members
          </h1>
          <p className="mt-2 text-slate-400">
            Verify duplicate profile identities and assign administrative keywords
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {loading && <p className="text-center text-slate-400 py-12">Loading members…</p>}
        {error && <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-red-300 mb-6">{error}</div>}

        {!loading && !error && (
          <div className="flex flex-col gap-4">
            {members.map((member) => (
              <div
                key={member.id}
                className={`flex flex-wrap items-center justify-between gap-4 p-5 rounded-xl border transition-colors ${
                  member.is_validated
                    ? "border-slate-800 bg-slate-900/40"
                    : "border-amber-500/40 bg-amber-500/5"
                }`}
              >
                <div>
                  <h3 className="text-lg font-semibold text-white">{member.nome_completo}</h3>
                  <span className={`text-xs font-bold uppercase tracking-wider ${member.is_validated ? "text-green-500" : "text-amber-500"}`}>
                    {member.is_validated ? "✓ Validated" : "⚠️ Review Required (Clone)"}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <input
                    type="text"
                    placeholder="Alcunha (e.g. BTT, Triatleta)"
                    value={member.keyword || ""}
                    onChange={(e) => handleKeywordChange(member.id, e.target.value)}
                    className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600 outline-none focus:border-[#fc4c02]/50"
                  />
                  <button
                    type="button"
                    onClick={() => handleValidate(member.id, member.keyword)}
                    className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                      member.is_validated
                        ? "bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700"
                        : "bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold"
                    }`}
                  >
                    {member.is_validated ? "Update" : "Validate Identity"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
