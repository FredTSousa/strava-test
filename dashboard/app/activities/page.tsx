
'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

interface Activity {
  id_virtual: string;
  raw_json: any;
  assigned_member_id: number | null;
}

interface Member {
  id: number;
  nome_completo: string;
  keyword: string | null;
}

export default function ActivitiesPage() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  async function loadCuratorData() {
    setLoading(true);
    
    // Procura atividades cujo Foreign Key está nulo (Is Null / Left Join órfão)
    const { data: acts } = await supabase
      .from('strava_raw_feed')
      .select('*')
      .is('assigned_member_id', null);

    const { data: membs } = await supabase
      .from('club_members')
      .select('id, nome_completo, keyword');

    if (acts) setActivities(acts as Activity[]);
    if (membs) setMembers(membs as Member[]);
    setLoading(false);
  }

  useEffect(() => {
    loadCuratorData();
  }, []);

  const handleAssign = async (idVirtual: string, memberId: number) => {
    const { error } = await supabase
      .from('strava_raw_feed')
      .update({ assigned_member_id: memberId })
      .eq('id_virtual', idVirtual);

    if (!error) {
      // Remove do Estado Local (Ajax-Refresh visual) para o card desaparecer do ecrã
      setActivities(prev => prev.filter(act => act.id_virtual !== idVirtual));
    } else {
      alert('Erro ao atribuir: ' + error.message);
    }
  };

  if (loading) return <div className="p-8">A carregar atividades...</div>;

  return (
    <div className="p-8 max-w-5xl mx-auto font-sans">
      <h1 className="text-2xl font-bold mb-2">🏃‍♂️ Curadoria de Atividades Pendentes</h1>
      <p className="text-gray-600 mb-6">Filtro de integridade: atribui os treinos dos clones ao ID real correto.</p>

      {activities.length === 0 ? (
        <div className="p-6 bg-green-50 border border-green-200 text-green-800 rounded-lg font-semibold">
          ✓ Excelente! Não há treinos ambíguos por resolver.
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {activities.map((act) => {
            const raw = act.raw_json;
            const athleteName = `${raw.athlete?.firstname || ''} ${raw.athlete?.lastname || ''}`.trim() || "Desconhecido";
            
            // Lógica de Intersecção: cruza a string do Strava com a nossa tabela
            const matchingMembers = members.filter(m => m.nome_completo === athleteName);

            return (
              <div key={act.id_virtual} className="p-5 border border-gray-200 rounded-lg bg-white shadow-sm">
                <div className="mb-4">
                  <h3 className="text-lg font-bold text-gray-900">{raw.name || 'Treino s/ Nome'}</h3>
                  <p className="text-sm text-gray-500">
                    Atleta Strava: <span className="font-semibold text-gray-700">{athleteName}</span> | 
                    Distância: {(raw.distance / 1000).toFixed(2)} km
                  </p>
                </div>

                <div className="bg-gray-50 p-4 rounded-md border border-gray-150">
                  <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">A quem pertence esta atividade?</p>
                  <div className="flex gap-2 flex-wrap">
                    {matchingMembers.length === 0 ? (
                      <span className="text-sm text-red-500">⚠️ Nome não encontrado no banco. Sincronize os membros primeiro.</span>
                    ) : (
                      matchingMembers.map(member => (
                        <button
                          key={member.id}
                          onClick={() => handleAssign(act.id_virtual, member.id)}
                          className="px-3 py-2 bg-blue-50 hover:bg-blue-100 border border-blue-300 text-blue-700 rounded text-sm font-medium transition-colors"
                        >
                          {member.nome_completo} ({member.keyword || 'S/ Keyword'})
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
    </div>
  );
}
