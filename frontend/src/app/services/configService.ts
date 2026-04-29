import { apiGet, apiPostJson } from "./apiClient";
import type {
  ConfigRevisionActivationResponse,
  ConfigRevisionCreateResponse,
  ConfigRevisionDTO,
  ConfigRevisionPage,
  ConfigReleaseRecordDTO,
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

export async function fetchConfigReleaseRecords(kbId: string): Promise<ConfigReleaseRecordDTO[]> {
  return apiGet<ConfigReleaseRecordDTO[]>(`/knowledge-bases/${kbId}/config-revisions/release-records`);
}

export async function createConfigReleaseRecord(
  kbId: string,
  revisionId: string,
  changeSummary: string,
  rollbackPlan?: string,
): Promise<ConfigReleaseRecordDTO> {
  return apiPostJson<ConfigReleaseRecordDTO>(
    `/knowledge-bases/${kbId}/config-revisions/${revisionId}/release-records`,
    { changeSummary, rollbackPlan },
  );
}

export async function confirmConfigRollback(
  kbId: string,
  revisionId: string,
  reason: string,
  targetRevisionId?: string,
): Promise<ConfigReleaseRecordDTO> {
  return apiPostJson<ConfigReleaseRecordDTO>(
    `/knowledge-bases/${kbId}/config-revisions/${revisionId}/rollback-confirmation`,
    { confirmImpact: true, reason, targetRevisionId },
  );
}
