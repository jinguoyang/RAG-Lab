import { apiGet } from "./apiClient";
import type { AgentScenarioTemplateDTO } from "../types/agentScenario";

export async function listAgentScenarioTemplates(): Promise<AgentScenarioTemplateDTO[]> {
  return apiGet<AgentScenarioTemplateDTO[]>("/agent-scenario-templates");
}
