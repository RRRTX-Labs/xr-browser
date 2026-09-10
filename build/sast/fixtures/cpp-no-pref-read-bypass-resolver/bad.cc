// SAST canary fixture — cpp-no-pref-read-bypass-resolver.
// Never built/shipped; proves the rule can turn red: a direct preference
// read used to make a policy decision outside the resolver.
#include <string>

bool DecideFromPrefs() {
  // banned: direct pref reads bypassing Resolve()
  const bool strict = prefs::GetBoolean("xr.strict_mode");
  return strict;
}
