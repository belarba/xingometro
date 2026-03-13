import { useState, useEffect } from "react";
import { fetchRounds } from "../services/api";

interface RoundFilterProps {
  selectedRound: number | null;
  onRoundChange: (round: number | null) => void;
}

export default function RoundFilter({
  selectedRound,
  onRoundChange,
}: RoundFilterProps) {
  const [rounds, setRounds] = useState<number[]>([]);

  useEffect(() => {
    fetchRounds()
      .then(setRounds)
      .catch(() => {});
  }, []);

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-gray-400">Rodada:</label>
      <select
        value={selectedRound ?? ""}
        onChange={(e) => {
          const val = e.target.value;
          onRoundChange(val === "" ? null : Number(val));
        }}
        className="bg-white/[0.05] border border-white/[0.1] rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-white/20"
      >
        <option value="">Todas</option>
        {rounds.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
    </div>
  );
}
