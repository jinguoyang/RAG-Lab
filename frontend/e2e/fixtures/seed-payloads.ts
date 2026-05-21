export const BASE_SEED = {
  users: [
    { username: "admin", platform_role: "platform_admin" },
    { username: "lib_owner", platform_role: "platform_user" },
    { username: "lib_viewer", platform_role: "platform_user" },
    { username: "kb_editor", platform_role: "platform_user" },
  ],
  libraries: [
    {
      name: "e2e-test-library",
      members: [
        { username: "admin", role: "library_owner" },
        { username: "lib_owner", role: "library_owner" },
        { username: "lib_viewer", role: "library_viewer" },
      ],
    },
  ],
  knowledge_bases: [
    {
      name: "e2e-test-kb",
      library_name: "e2e-test-library",
      members: [
        { username: "admin", role: "kb_owner" },
        { username: "lib_owner", role: "kb_owner" },
        { username: "kb_editor", role: "kb_editor" },
      ],
    },
  ],
};
