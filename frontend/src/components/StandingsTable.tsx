import { useState, useEffect } from "react";
import { fetchStandings } from "../services/api";
import type { StandingEntry } from "../types";

function getZoneColor(position: number): string {
  if (position <= 4) return "border-l-blue-500";
  if (position <= 6) return "border-l-green-500";
  if (position >= 17) return "border-l-red-500";
  return "border-l-transparent";
}

export default function StandingsTable() {
  const [standings, setStandings] = useState<StandingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadStandings = () => {
    setLoading(true);
    setError(false);
    fetchStandings()
      .then((data) => {
        setStandings(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadStandings();
  }, []);

  if (loading) {
    return (
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
        <p className="text-gray-500 text-sm">Carregando...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-4">Classificação</h2>
        <p className="text-gray-500 text-sm">
          Erro ao carregar dados.{" "}
          <button onClick={loadStandings} className="text-red-400 underline">
            Tentar novamente
          </button>
        </p>
      </div>
    );
  }

  if (standings.length === 0) {
    return (
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-4">Classificação</h2>
        <p className="text-gray-500 text-sm">Classificação indisponível</p>
      </div>
    );
  }

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4">Brasileirão Série A 2026</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-left border-b border-white/[0.08]">
              <th className="py-2 px-1 w-8">#</th>
              <th className="py-2 px-1">Time</th>
              <th className="py-2 px-1 text-center w-8">P</th>
              <th className="py-2 px-1 text-center w-8">J</th>
              <th className="py-2 px-1 text-center w-8">V</th>
              <th className="py-2 px-1 text-center w-8">E</th>
              <th className="py-2 px-1 text-center w-8">D</th>
              <th className="py-2 px-1 text-center w-8">GP</th>
              <th className="py-2 px-1 text-center w-8">GC</th>
              <th className="py-2 px-1 text-center w-8">SG</th>
            </tr>
          </thead>
          <tbody>
            {standings.map((entry) => (
              <tr
                key={entry.position}
                className={`border-b border-white/[0.04] border-l-[3px] ${getZoneColor(entry.position)} hover:bg-white/[0.03] transition-colors`}
              >
                <td className="py-2 px-1 text-gray-500">{entry.position}</td>
                <td className="py-2 px-1 font-medium">
                  {entry.short_name || entry.team_name}
                </td>
                <td className="py-2 px-1 text-center font-bold">{entry.points}</td>
                <td className="py-2 px-1 text-center text-gray-400">{entry.played_games}</td>
                <td className="py-2 px-1 text-center text-gray-400">{entry.won}</td>
                <td className="py-2 px-1 text-center text-gray-400">{entry.draw}</td>
                <td className="py-2 px-1 text-center text-gray-400">{entry.lost}</td>
                <td className="py-2 px-1 text-center text-gray-400">{entry.goals_for}</td>
                <td className="py-2 px-1 text-center text-gray-400">{entry.goals_against}</td>
                <td
                  className={`py-2 px-1 text-center ${
                    entry.goal_difference > 0
                      ? "text-green-400"
                      : entry.goal_difference < 0
                        ? "text-red-400"
                        : "text-gray-400"
                  }`}
                >
                  {entry.goal_difference > 0 ? "+" : ""}
                  {entry.goal_difference}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex gap-4 text-xs text-gray-500">
        <span>
          <span className="inline-block w-2 h-2 bg-blue-500 rounded-sm mr-1" />
          Libertadores
        </span>
        <span>
          <span className="inline-block w-2 h-2 bg-green-500 rounded-sm mr-1" />
          Sul-Americana
        </span>
        <span>
          <span className="inline-block w-2 h-2 bg-red-500 rounded-sm mr-1" />
          Rebaixamento
        </span>
      </div>
    </div>
  );
}
