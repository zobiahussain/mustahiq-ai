// Shared across every screen so the branding is consistent everywhere.
// Al-Khidmat logo + product name, mirroring the staff portal's co-brand
// (apps/main-portal) so the two apps read as one product. Each screen
// still gets its own subtitle via `subtitle`.
export default function Header({ subtitle, subtitleUr }) {
  return (
    <>
      <div className="app-header">
        <span className="app-brand">
          <img className="app-logo" src="/alkhidmat-logo.svg" alt="Al-Khidmat Foundation Pakistan" />
          <span className="app-title">
            Mustahiq<span className="app-title-accent">AI</span> Marketplace
          </span>
        </span>
        <span className="app-title-ur">مستحق بازار</span>
      </div>
      {subtitle && (
        <h2 className="card-heading" style={{ marginBottom: 20 }}>
          {subtitle} {subtitleUr && <span className="ur">{subtitleUr}</span>}
        </h2>
      )}
    </>
  );
}
