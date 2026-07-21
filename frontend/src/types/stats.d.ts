export interface Overview {
  qa_total: number
  session_total: number
  user_total: number
  entity_total: number
}

export interface LocationFrequencyItem {
  name: string
  display_name: string
  count: number
  type: string
  address: string
}

export interface TypeDistributionItem {
  type: string
  count: number
}

export interface DailyTrendItem {
  date: string
  count: number
}

export interface LocationFrequency {
  total_qa: number
  top_locations: LocationFrequencyItem[]
  type_distribution: TypeDistributionItem[]
  daily_trend: DailyTrendItem[]
}
