
'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';

// Inicializa o cliente Supabase usando as variáveis de ambiente locais do Next.js
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

interface Member {
  id: number;
  nome_completo: string;
  keyword: string | null;
  is_validated: boolean;
}

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Equivalente ao "Preparation" ou "OnReady" Action do OutSystems
  async function fetchMembers() {
    setLoading(true);
    const { data, error } = await supabase
      .from('club_members')
      .select('*')
      .order('nome_completo', { ascending: true });

    if (!error && data) {
      setMembers(data as Member[]);
    }
    setLoading(false);
  }

  useEffect(() => {
    fetchMembers();
  }, []);

  const handleKeywordChange = (id: number, newKeyword: string) => {
    setMembers(prev => prev.map(m => (m.id === id ? { ...m, keyword: newKeyword } : m)));
  };

  // Screen Action para dar o Update na linha da Base de Dados
  const handleSaveAndValidate = async (id: number, keyword: string | null) => {
    const { error } = await supabase
      .from('club_members')
      .update({ keyword: keyword, is_validated: true })
      .eq('id', id);

    if (error) {
      alert('Erro ao guardar: ' + error.message);
    } else {
      fetchMembers(); // Dá um refresh implícito aos dados do ecrã
    }
  };

  if (loading) return <div className="p-8">A carregar membros...</div>;

  return (
    <div className="p-8 max-w-4xl mx-auto font-sans">
      <h1 className="text-2xl font-bold mb-2">👤 Gestão de Membros do Clube</h1>
      <p className="text-gray-600 mb-6">Valida os novos clones detetados pelo script e define as suas keywords.</p>

      <div className="flex flex-col gap-4">
        {members.map((member) => (
          <div
            key={member.id}
            className={`flex items-center justify-between p-5 rounded-lg border transition-all ${
              member.is_validated ? 'bg-white border-gray-200' : 'bg-yellow-50 border-yellow-300'
            }`}
          >
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{member.nome_completo}</h3>
              <span className={`text-sm font-bold ${member.is_validated ? 'text-green-600' : 'text-amber-600'}`}>
                {member.is_validated ? '✓ Validado' : '⚠️ Clone Pendente de Revisão'}
              </span>
            </div>

            <div className="flex gap-3 items-center">
              <input
                type="text"
                placeholder="Ex: Maratonista, BTT..."
                value={member.keyword || ''}
                onChange={(e) => handleKeywordChange(member.id, e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
              />
              <button
                onClick={() => handleSaveAndValidate(member.id, member.keyword)}
                className={`px-4 py-2 rounded-md font-bold text-sm transition-colors ${
                  member.is_validated 
                    ? 'bg-blue-600 hover:bg-blue-700 text-white' 
                    : 'bg-amber-500 hover:bg-amber-600 text-black'
                }`}
              >
                {member.is_validated ? 'Atualizar' : 'Validar Membro'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
