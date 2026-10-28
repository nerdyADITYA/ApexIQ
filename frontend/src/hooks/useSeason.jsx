import { createContext, useContext, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api.js'

const SeasonContext = createContext(null)

export function SeasonProvider({ children }) {
  const { data } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const years = (data ?? []).map((s) => s.year)
  const [year, setYear] = useState(null)

  useEffect(() => {
    if (year === null && years.length) setYear(years[0])
  }, [year, years])

  return (
    <SeasonContext.Provider value={{ year, setYear, years }}>{children}</SeasonContext.Provider>
  )
}

export const useSeason = () => useContext(SeasonContext)
