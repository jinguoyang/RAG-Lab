import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

function read(path) {
  return readFileSync(resolve(root, path), "utf8");
}

function assertContains(file, text) {
  const content = read(file);
  if (!content.includes(text)) {
    throw new Error(`${file} is missing ${text}`);
  }
}

assertContains("src/app/services/dictionaryService.ts", "fetchDictionaryItems");
assertContains("src/app/services/dictionaryService.ts", "SYSTEM_DICTIONARY_FALLBACKS");
assertContains("src/app/services/dictionaryService.ts", "chooseActiveDictionaryValue");
assertContains("src/app/types/dictionary.ts", "DictionaryItemDTO");
assertContains("src/app/pages/P14_DictionaryManagement.tsx", "DictionaryManagement");
assertContains("src/app/routes.tsx", "DictionaryManagement");
assertContains("src/app/layouts/PlatformLayout.tsx", "/dictionaries");
assertContains("src/app/pages/P03_UserManagement.tsx", "fetchDictionaryBundle([\"platform_role\", \"security_level\"])");
assertContains("src/app/pages/P10_QAHistory.tsx", "fetchDictionaryItemsWithFallback(\"feedback_status\")");
assertContains("src/app/pages/P12_MembersAndPermissions.tsx", "fetchDictionaryItemsWithFallback(\"kb_role\")");
assertContains("src/app/pages/P13_RagAppManagement.tsx", "fetchDictionaryItemsWithFallback(\"feedback_status\")");
assertContains("src/app/pages/P03_UserManagement.tsx", "chooseActiveDictionaryValue");
assertContains("src/app/pages/P13_RagAppManagement.tsx", "chooseActiveDictionaryValue");

console.log("system dictionary frontend wiring verified");
