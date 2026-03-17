interface TabNavProps {
  activeTab: "xingometro" | "classificacao";
  onTabChange: (tab: "xingometro" | "classificacao") => void;
}

export default function TabNav({ activeTab, onTabChange }: TabNavProps) {
  const tabs = [
    { key: "xingometro" as const, label: "Xingômetro" },
    { key: "classificacao" as const, label: "Classificação" },
  ];

  return (
    <div className="flex gap-0 border-b border-white/[0.08] px-6">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onTabChange(tab.key)}
          className={`px-5 py-3 text-sm font-medium transition-colors ${
            activeTab === tab.key
              ? "text-white border-b-2 border-red-500"
              : "text-gray-500 hover:text-gray-300"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
