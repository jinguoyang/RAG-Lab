export interface AgentScenarioFieldOptionDTO {
  label: string;
  value: string | number | boolean;
}

export interface AgentScenarioConfigFieldDTO {
  name: string;
  label: string;
  fieldType: string;
  defaultValue: string | number | boolean | null;
  options: AgentScenarioFieldOptionDTO[];
  description: string | null;
  required: boolean;
}

export interface AgentScenarioTemplateDTO {
  templateId: string;
  scenarioType: "knowledge_qa" | "employee_training" | string;
  name: string;
  description: string;
  defaultConfig: Record<string, unknown>;
  defaultPublishChannels: Record<string, boolean>;
  defaultEmbedSettings: Record<string, unknown>;
  configFields: AgentScenarioConfigFieldDTO[];
}
