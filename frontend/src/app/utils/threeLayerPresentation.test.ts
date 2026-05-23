import { describe, expect, it } from "vitest";
import {
  chunkRevisionStatusLabel,
  chunkRevisionStatusVariant,
  layerLabel,
  permissionSourceLabel,
} from "./threeLayerPresentation";

describe("threeLayerPresentation", () => {
  it("maps ChunkRevision statuses to stable Chinese labels and badge variants", () => {
    expect(chunkRevisionStatusLabel("building")).toBe("构建中");
    expect(chunkRevisionStatusVariant("building")).toBe("running");
    expect(chunkRevisionStatusLabel("active")).toBe("已激活");
    expect(chunkRevisionStatusVariant("active")).toBe("success");
    expect(chunkRevisionStatusLabel("retired")).toBe("已退役");
    expect(chunkRevisionStatusVariant("retired")).toBe("inactive");
    expect(chunkRevisionStatusLabel("failed")).toBe("构建失败");
    expect(chunkRevisionStatusVariant("failed")).toBe("error");
  });

  it("keeps unknown ChunkRevision status visible instead of hiding it", () => {
    expect(chunkRevisionStatusLabel("paused")).toBe("paused");
    expect(chunkRevisionStatusVariant("paused")).toBe("default");
  });

  it("names the three product layers consistently", () => {
    expect(layerLabel("library")).toBe("文档库");
    expect(layerLabel("knowledgeBase")).toBe("知识库");
    expect(layerLabel("app")).toBe("智能应用");
  });

  it("explains permission sources with direct, group, platform, and deny wording", () => {
    expect(permissionSourceLabel({ sourceType: "directKbRole", sourceName: null, roleCode: "kb_editor", effect: "allow" })).toBe(
      "直接授权：kb_editor",
    );
    expect(permissionSourceLabel({ sourceType: "groupKbRole", sourceName: "运营组", roleCode: "kb_viewer", effect: "allow" })).toBe(
      "用户组继承：运营组 / kb_viewer",
    );
    expect(permissionSourceLabel({ sourceType: "platformRole", sourceName: null, roleCode: "platform_admin", effect: "allow" })).toBe(
      "平台角色：platform_admin",
    );
    expect(permissionSourceLabel({ sourceType: "groupKbRole", sourceName: "访客组", roleCode: "kb_viewer", effect: "deny" })).toBe(
      "Deny：用户组继承：访客组 / kb_viewer",
    );
  });
});
