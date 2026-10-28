/** Full names for the short session codes stored by the API. */
const NAMES = {
  R: 'Race',
  Q: 'Qualifying',
  S: 'Sprint',
  SQ: 'Sprint qualifying',
  SS: 'Sprint shootout', // the 2023 name for sprint qualifying
  FP1: 'Practice 1',
  FP2: 'Practice 2',
  FP3: 'Practice 3',
}

export const sessionName = (type) => NAMES[type] ?? type
