/**
 * Typed domain contracts for Core Business Analytics and reporting.
 */

export interface EvidenceMetadata {
  source_record_ids: string[];
  date_window_start?: string | null;
  date_window_end?: string | null;
  calculation_method: string;
  assumptions: string[];
  freshness_timestamp: string;
  warnings: string[];
}

export interface DomainResult<T> {
  data: T;
  evidence: EvidenceMetadata;
}

export interface KPIOverview {
  gross_revenue: string | number;
  sales_returns: string | number;
  net_revenue: string | number;
  cogs?: string | number | null;
  gross_profit?: string | number | null;
  gross_margin_pct?: string | number | null;
  total_units_sold: string | number;
  transaction_count: number;
  total_expenses: string | number;
  net_profit_estimate?: string | number | null;
  inventory_valuation: string | number;
  inventory_turnover?: string | number | null;
  missing_cost_items_count: number;
  cost_data_available: boolean;
  currency: string;
  period_label: string;
}

export interface ProductPerformanceItem {
  product_id: string;
  product_name: string;
  sku?: string | null;
  category_name?: string | null;
  unit: string;
  units_sold: string | number;
  revenue: string | number;
  cogs?: string | number | null;
  gross_profit?: string | number | null;
  gross_margin_pct?: string | number | null;
  has_cost_price: boolean;
}

export interface ProductRankingResponse {
  top_by_revenue: ProductPerformanceItem[];
  top_by_units: ProductPerformanceItem[];
  top_by_profit: ProductPerformanceItem[];
  slow_moving: ProductPerformanceItem[];
}

export interface CategoryPerformanceItem {
  category_id?: string | null;
  category_name: string;
  units_sold: string | number;
  revenue: string | number;
  cogs?: string | number | null;
  gross_profit?: string | number | null;
  gross_margin_pct?: string | number | null;
  product_count: number;
}

export interface CategoryBreakdownResponse {
  categories: CategoryPerformanceItem[];
  total_revenue: string | number;
}

export interface AnalyticsTrendPoint {
  date: string;
  gross_revenue: string | number;
  net_revenue: string | number;
  cogs?: string | number | null;
  gross_profit?: string | number | null;
  expenses: string | number;
  units_sold: string | number;
  transaction_count: number;
}

export interface AnalyticsTrendsResponse {
  period_label: string;
  points: AnalyticsTrendPoint[];
  total_revenue: string | number;
  total_expenses: string | number;
}
