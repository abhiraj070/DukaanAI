/**
 * TypeScript types for What-if Decision Simulation and Scenario Modeling.
 */

export interface ScenarioItemInput {
  product_id: string;
  price_delta_pct?: number | null;
  cost_delta_pct?: number | null;
  demand_delta_pct?: number | null;
}

export interface ScenarioInput {
  scenario_name: string;
  time_horizon_days?: number;
  general_demand_uplift_pct?: number;
  expected_udhar_collections?: number;
  purchase_cash_outflow?: number;
  supply_delay_days?: number;
  items?: ScenarioItemInput[];
}

export interface SimulationMetricDelta {
  baseline: number;
  simulated: number;
  delta_amount: number;
  delta_pct?: number | null;
}

export interface SimulationResult {
  scenario_name: string;
  time_horizon_days: number;
  revenue: SimulationMetricDelta;
  cogs?: SimulationMetricDelta | null;
  gross_profit?: SimulationMetricDelta | null;
  cash_collected_estimate: number;
  purchase_cash_outflow: number;
  supply_delay_days: number;
  assumptions_applied: string[];
  constraints_and_risks: string[];
  model_version: string;
}

export interface SavedScenario {
  id: string;
  scenario_name: string;
  model_version: string;
  created_at: string;
  input: ScenarioInput;
  result: SimulationResult;
  evidence: {
    source_record_ids: string[];
    date_window_start?: string | null;
    date_window_end?: string | null;
    calculation_method: string;
    assumptions: string[];
    freshness_timestamp: string;
    warnings: string[];
  };
}
