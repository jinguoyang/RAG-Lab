import { describe, expect, it } from "vitest";
import {
  bindingRevisionStatusLabel,
  bindingRevisionStatusVariant,
  layerLabel,
  permissionSourceLabel,
} from "./threeLayerPresentation";

describe("threeLayerPresentation", () => {
  it("maps BindingRevision statuses to stable Chinese labels and badge variants", () => {
    expect(bindingRevisionStatusLabel("building")).toBe("构建中");
    expect(bindingRevisionStatusVariant("building")).toBe("running");
    expect(bindingRevisionStatusLabel("active")).toBe("已激活");
    expect(bindingRevisionStatusVariant("active")).toBe("success");
    expect(bindingRevisionStatusLabel("retired")).toBe("已退役");
    expect(bindingRevisionStatusVariant("retired")).toBe("inactive");
    expect(bindingRevisionStatusLabel("failed")).toBe("构建失败");
    expect(bindingRevisionStatusVariant("failed")).toBe("error");
  });

  it("keeps unknown BindingRevision status visible instead of hiding it", () => {
    expect(bindingRevisionStatusLabel("paused")).toBe("paused");
    expect(bindingRevisionStatusVariant("paused")).toBe("default");
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
