type StatCardProps = {
  label: string;
  value: string | number;
  tone?: "neutral" | "good" | "warning" | "bad";
};

export function StatCard({ label, value, tone = "neutral" }: StatCardProps) {
  return (
    <section className={`stat-card ${tone}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </section>
  );
}
