"use client";
import { useState } from "react";
import { getSupabase } from "../utils/supabase";

export default function Login({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const db = getSupabase();
    const { error } = await db.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      onLoginSuccess();
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
      <form onSubmit={handleLogin} className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <h2 className="text-xl font-bold text-white mb-4 text-center">Movera Run Club Admin</h2>
        
        {error && <p className="mb-4 rounded bg-red-950/40 p-2.5 text-xs text-red-400 border border-red-900/30">{error}</p>}
        
        <div className="mb-4">
          <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-[#fc4c02]/50" />
        </div>

        <div className="mb-6">
          <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-[#fc4c02]/50" />
        </div>

        <button type="submit" disabled={loading} className="w-full rounded-lg bg-[#fc4c02] py-2 text-sm font-bold text-white hover:bg-[#e04302] transition disabled:opacity-50">
          {loading ? "A entrar..." : "Entrar"}
        </button>
      </form>
    </div>
  );
}
