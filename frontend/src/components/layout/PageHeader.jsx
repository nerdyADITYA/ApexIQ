import { useSeason } from '../../hooks/useSeason.jsx'

/** A select with a visible caption above it, so every control in the header says what it is. */
export function Field({ label, children }) {
  return (
    <label className="season-picker field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  )
}

function SeasonPicker() {
  const { year, setYear, years } = useSeason()
  return (
    <Field label="Season">
      <select value={year ?? ''} onChange={(e) => setYear(Number(e.target.value))}>
        {years.length === 0 && <option value="">none ingested</option>}
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </Field>
  )
}

/** Eyebrow + title on the left, labelled selectors on the right (matches the Pit wall mockup). */
export default function PageHeader({ eyebrow, title, children, noSeason = false, accent }) {
  return (
    <header className="pagebar">
      <div className={accent ? 'team-accent' : undefined} style={accent ? { '--team': accent } : undefined}>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
      </div>
      <div className="pagebar-right">
        {children}
        {!noSeason && <SeasonPicker />}
      </div>
    </header>
  )
}
