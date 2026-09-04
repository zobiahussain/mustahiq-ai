// Shared across every screen so the branding is consistent everywhere,
// not just redefined ad hoc per-file. "Mustahiq AI Marketplace" per the
// rename -- each screen still gets its own subtitle via `subtitle`.
export default function Header({ subtitle, subtitleUr }) {
  return (
    <>
      <div className="app-header">
        <span className="app-title">Mustahiq AI Marketplace</span>
        <span className="app-title-ur">مستحق مارکیٹ پلیس</span>
      </div>
      {subtitle && (
        <h2 className="card-heading" style={{ marginBottom: 20 }}>
          {subtitle} {subtitleUr && <span className="ur">{subtitleUr}</span>}
        </h2>
      )}
    </>
  );
}
