// libfuzzer_common.h — shared guard for the P9-T8 CI-side libFuzzer targets.
//
// These targets are built ONLY by the CI a11y/fuzz lane, which has clang +
// libFuzzer. They never build in the P9 sandbox (no clang here): when a
// non-libFuzzer toolchain compiles one of these files, the fallback main()
// prints a visible SKIP and exits 77 — a record, never a fake result.
//
// Usage (CI): clang++ -fsanitize=fuzzer,address -I../xr-core/<core>/core \
//   <target>.cc -o <target>
#ifndef XR_BUILD_FUZZ_LIBFUZZER_COMMON_H_
#define XR_BUILD_FUZZ_LIBFUZZER_COMMON_H_

#if defined(__clang__) && defined(LIBFUZZER_BUILD)
#define XR_HAS_LIBFUZZER 1
#include <cstddef>
#include <cstdint>
#else
#define XR_HAS_LIBFUZZER 0
#endif

#include <cstdio>
#include <cstdlib>

// Each target provides XrFuzzOneInput(data, size) — the code under test.
#if XR_HAS_LIBFUZZER
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  XrFuzzOneInput(data, size);
  return 0;
}
#else
// g++/msvc fallback: visible skip, exit 77. Never asserts a result.
int main() {
  std::fprintf(stderr,
               "SKIP: %s needs clang + libFuzzer (CI-side, HG-28); the "
               "in-house seeded fuzzer is the gate lane. exit 77\n",
               XR_LIBFUZZER_TARGET_NAME);
  return 77;
}
#endif

#endif  // XR_BUILD_FUZZ_LIBFUZZER_COMMON_H_
