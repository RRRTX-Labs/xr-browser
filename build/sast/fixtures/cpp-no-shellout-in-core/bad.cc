// SAST canary fixture — cpp-no-shellout-in-core.
// Never built/shipped; proves the rule can turn red.
#include <cstdlib>

int trigger() {
  return system("rm -rf /tmp/x");   // banned: shell-out in a core path
}
