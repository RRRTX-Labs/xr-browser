// SAST canary fixture — cpp-memory-unsafe-stdlib.
// This file exists ONLY to prove the rule can turn red: it contains the
// banned literal patterns and is never built or shipped. The real scan
// (tools/sast_check.py) excludes build/sast/fixtures/ by scope.
#include <cstdio>

void trigger(const char* src, char* dst) {
  strcpy(dst, src);          // banned: unchecked copy
  strcat(dst, "-suffix");    // banned: unchecked append
  sprintf(dst, "%s", src);   // banned: unchecked format
  gets(dst);                 // banned: removed from C11
}
