import { apiGet, apiPostJson } from "./apiClient";
import type {
  ConfigRevisionActivationResponse,
  ConfigRevisionCreateResponse,
  ConfigRevisionDTO,
  ConfigRevisionPage,
  PipelineDefinition,
  PipelineValidationResultDTO,
} from "../types/config";

export async function validatePipeline(
  kbId: string,
  pipelineDefinition: PipelineDefinition,
): Promise<PipelineValidationResultDTO> {
  return apiPostJson<PipelineValidationResultDTO>(
    `/knowledge-bases/${kbId}/config-revisions/validate`,
    { pipelineDefinition },
  );
}

export async function saveConfigRevision(
  kbId: string,
  pipelineDefinition: PipelineDefinition,
  remark: string,
): Promise<ConfigRevisionCreateResponse> {
  return apiPostJson<ConfigRevisionCreateResponse>(
    `/knowledge-bases/${kbId}/config-revisions`,
    { pipelineDefinition, remark },
  );
}

export async function fetchConfigRevisions(kbId: string): Promise<ConfigRevisionPage> {
  return apiGet<ConfigRevisionPage>(
    `/knowledge-bases/${kbId}/config-revisions?pageNo=1&pageSize=50`,
  );
}

export async function activateConfigRevision(
  kbId: string,
  revisionId: string,
): Promise<ConfigRevisionActivationResponse> {
  return apiPostJson<ConfigRevisionActivationResponse>(
    `/knowledge-bases/${kbId}/config-revisions/${revisionId}/activate`,
    { confirmImpact: true, reason: "P08 配置中心切换生效版本" },
  );
}

export async function copyConfigRevisionToDraft(
  kbId: string,
  sourceRevisionId: string,
): Promise<ConfigRevisionDTO> {
  return apiPostJson<ConfigRevisionDTO>(
    `/knowledge-bases/${kbId}/config-revisions/drafts/from-revision`,
    { sourceRevisionId, remark: "P08 从历史 Revision 复制为草稿" },
  );
}
