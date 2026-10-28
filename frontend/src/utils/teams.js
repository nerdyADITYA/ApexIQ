/** Team colours for stripes, bars and chart lines. Colour is never the only cue: labels always accompany it. */
const TEAM_COLORS = {
  Mercedes: '#27F4D2',
  Ferrari: '#E8002D',
  McLaren: '#FF8000',
  'Red Bull Racing': '#3671C6',
  'Racing Bulls': '#6692FF',
  RB: '#6692FF',
  AlphaTauri: '#6692FF',
  'Aston Martin': '#229971',
  Alpine: '#FF87BC',
  Williams: '#64C4FF',
  'Haas F1 Team': '#B6BABD',
  'Kick Sauber': '#52E252',
  'Alfa Romeo': '#C92D4B',
  Audi: '#B07CFF',
  Cadillac: '#E0E0E0',
}

export const FALLBACK_COLOR = '#8a93a3'

export function teamColor(team) {
  return TEAM_COLORS[team] ?? FALLBACK_COLOR
}

/** "Red Bull Racing" -> "Red Bull"; keeps compact labels in tight bars. */
export function shortTeam(team) {
  if (!team) return '—'
  return team.replace(' Racing', '').replace(' F1 Team', '')
}
