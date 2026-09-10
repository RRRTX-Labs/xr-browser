// SAST canary fixture — cpp-mode-logic-outside-resolver.
// Never built/shipped; proves mode_lint can turn red: a subsystem file that
// references resolver-input tokens to make its own decision is a "second
// brain" and must fail the build.
#include <string>

bool SubsystemDecides(const std::string& trust_context) {
  // banned: private mode logic outside //xr/policy
  if (trust_context == "kFortress") return true;
  return false;
}
