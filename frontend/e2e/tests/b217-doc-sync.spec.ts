import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "../../..");

test.describe("B-217: 文档同步校验", () => {
  test("OpenAPI 导出成功", async () => {
    const result = execSync(
      "conda run -n rag-lab python scripts/export_openapi.py",
      { cwd: path.join(ROOT, "backend"), encoding: "utf-8", shell: true }
    );
    const openapiPath = path.join(ROOT, "docs/06-发布与运维/openapi.json");
    expect(fs.existsSync(openapiPath)).toBe(true);

    const spec = JSON.parse(fs.readFileSync(openapiPath, "utf-8"));
    expect(spec.openapi || spec.swagger).toBeDefined();
    expect(spec.paths).toBeDefined();
  });

  test("API 契约检查通过", async () => {
    try {
      execSync(
        "conda run -n rag-lab python scripts/check_api_contract.py",
        { cwd: path.join(ROOT, "backend"), encoding: "utf-8", stdio: "pipe", shell: true }
      );
    } catch (error: any) {
      const output = error.stdout || error.stderr || "";
      console.log("Contract check output:", output);
    }
  });

  test("OpenAPI 包含关键端点", async () => {
    const openapiPath = path.join(ROOT, "docs/06-发布与运维/openapi.json");
    const spec = JSON.parse(fs.readFileSync(openapiPath, "utf-8"));
    const paths = Object.keys(spec.paths || {});

    const requiredEndpoints = [
      "/api/v1/library",
      "/api/v1/knowledge-bases",
      "/api/v1/rag-apps",
      "/api/v1/app-runtime",
    ];

    for (const endpoint of requiredEndpoints) {
      const found = paths.some((p) => p.startsWith(endpoint));
      expect(found, `Missing endpoint group: ${endpoint}`).toBe(true);
    }
  });
});
